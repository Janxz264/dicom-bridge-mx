import oracledb as cx_Oracle  # for minimal disruption
import json
import logging
from pydicom.dataset import Dataset
from pynetdicom import AE, evt, debug_logger
from pynetdicom.sop_class import (
        ModalityWorklistInformationFind,
        Verification,
        SecondaryCaptureImageStorage,
        XRayRadiofluoroscopicImageStorage,
        ComputedRadiographyImageStorage,
        DigitalXRayImageStorageForPresentation,
        XRayAngiographicImageStorage,
        EncapsulatedPDFStorage,
        XRayRadiationDoseSRStorage
    )
     
# Configure logging (adjust as needed)
logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s: %(message)s",
        handlers=[logging.StreamHandler()]
    )
logger = logging.getLogger(__name__)
     
    # Optionally enable debug logging from pynetdicom
debug_logger()
     
    # Load database configuration
try:
        with open("db_config.json", "r") as config_file:
            config = json.load(config_file)
        logger.info("Loaded configuration from db_config.json")
except Exception as e:
        logger.exception("Failed to load configuration: %s", e)
        raise
     
# Extract Oracle connection settings from JSON
oracle_config = config["oracle"]
ORACLE_HOST = oracle_config["host"]
ORACLE_PORT = oracle_config["port"]
ORACLE_SERVICE_NAME = oracle_config["service_name"]
ORACLE_USERNAME = oracle_config["username"]
ORACLE_PASSWORD = oracle_config["password"]
     
# (The modality configuration file is now discarded.)
     
# Load Orthanc forward connection configuration
try:
        with open("forward_orthanc_connection.json", "r") as orthanc_file:
            orthanc_config = json.load(orthanc_file)
        logger.info("Loaded Orthanc connection configuration from forward_orthanc_connection.json")
except Exception as e:
        logger.exception("Failed to load Orthanc connection configuration: %s", e)
        orthanc_config = {}
     
    # Extract the Orthanc connection details
try:
        ORTHANC = orthanc_config["orthanc"]
        ORTHANC_HOST = ORTHANC["host"]
        ORTHANC_PORT = ORTHANC["port"]
        ORTHANC_AET = ORTHANC["ae_title"]
except Exception as e:
        logger.exception("Error extracting Orthanc connection settings: %s", e)
        # Optionally, set defaults or abort startup:
        ORTHANC_HOST = "localhost"
        ORTHANC_PORT = 4242
        ORTHANC_AET = "ORTHANC"
     
def get_worklist_from_db(requestor_ae):
        """Query database based on the incoming Requesting AE Title"""
        conn = None
        cursor = None
        try:
            logger.info("Connecting to Oracle: %s@%s:%s/%s",
                       ORACLE_USERNAME, ORACLE_HOST, ORACLE_PORT, ORACLE_SERVICE_NAME)
            
            # Choose ONE of these connection methods:
            
            # Method 1: Using makedsn (recommended)
            dsn = cx_Oracle.makedsn(ORACLE_HOST, ORACLE_PORT, service_name=ORACLE_SERVICE_NAME)
            conn = cx_Oracle.connect(
                user=ORACLE_USERNAME,
                password=ORACLE_PASSWORD,
                dsn=dsn
            )
            
            # OR Method 2: Easy Connect syntax
            #conn = cx_Oracle.connect(
            #    user=ORACLE_USERNAME,
            #    password=ORACLE_PASSWORD,
            #    dsn=f"{ORACLE_HOST}:{ORACLE_PORT}/{ORACLE_SERVICE_NAME}"
            #)
     
            
            cursor = conn.cursor()
            
            """Remember, this is where you use your custom SQL statement, so adapt this SQL SELECT as you need"""

            query = """
            SELECT DISTINCT 
                PATIENT_NAME, PERSONAL_ID, BENEFACTOR_ID,
                APPOINTMENT_DATE, HOUR, BIRTHDATE, SEX,
                MEDICAL_CENTER_ID, SPECIALTY_ID, STUDY_DESCRIPTION,
                APPOINTMENT_ID, PHYSICIAN_NAME, PHYSYCIAN_ID, ROOM, 
                ROOM_NUMBER, ROOM_LETTER, MEDICAL_CENTER_NAME, 
                PATIENT_ID, AETitle, ACCOUNT_NUMBER, SHIFT
            FROM RIS_WORKLIST_VIEW
            WHERE REGEXP_LIKE(AETitle, '(^|,)' || :aetitle || '(,|$)')
            ORDER BY HOUR ASC
            """
            logger.debug("Querying worklist for AE: %s (using exact match in comma-separated list)", requestor_ae)
            cursor.execute(query, aetitle=requestor_ae)
            return cursor.fetchall()
            
        except cx_Oracle.DatabaseError as e:
            error, = e.args
            logger.error("Oracle Error: %s (code: %s)", error.message, error.code)
            return []
        except Exception as e:
            logger.exception("Unexpected database error occurred")
            return []
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()
     
def handle_find(event):
        """Process C-FIND requests using RIS_WORKLIST_VIEW structure"""
        requestor_ae = event.assoc.requestor.ae_title
        logger.info("Received C-FIND from AE: %s", requestor_ae)

        responses = []
        worklist_entries = get_worklist_from_db(requestor_ae)

        if not worklist_entries:
            logger.info("No worklist entries found for AE: %s", requestor_ae)
            return [(0x0000, None)]

        for row in worklist_entries:
            ds = Dataset()
            ds.SpecificCharacterSet = "ISO_IR 100"
            appointment_id_str = str(row[10])

            # Patient Info
            ds.PatientID = str(row[17])
            full_name = row[0].strip()
            name_parts = full_name.split()

            if len(name_parts) >= 3:
                last_names = ' '.join(name_parts[-2:])
                first_names = ' '.join(name_parts[:-2])
                formatted_name = f"{last_names} {first_names}"
            else:
                formatted_name = full_name

            ds.PatientName = f"{formatted_name} - {row[18]}"
            ds.PatientBirthDate = row[5].strftime('%Y%m%d')
            ds.PatientSex = row[6]
            ds.PatientComments = f"ACCOUNT_NUMBER: {row[19]}"

            # Procedure Info
            ds.AccessionNumber = appointment_id_str.zfill(8)
            ds.RequestedProcedureID = appointment_id_str.zfill(6)
            ds.RequestedProcedureDescription = row[9]

            # UID Construction
            clean_pid = ds.PatientID.replace('_', '.')
            ds.StudyInstanceUID = f"1.2.3.{appointment_id_str}.{clean_pid}"
            ds.ReferringPhysicianName = row[11] if row[11] else "Unknown"

            # Scheduled Procedure Step
            sched = Dataset()
            sched.ScheduledProcedureStepStartDate = row[3].strftime('%Y%m%d')
            sched.ScheduledProcedureStepStartTime = row[4].replace(':', '')
            sched.ScheduledProcedureStepDescription = row[9]
            sched.ScheduledProcedureStepID = appointment_id_str
            sched.Modality = row[8]
            sched.ProcedureStepLocation = row[16]
            sched.ScheduledStationAETitle = row[18]

            # Physician Sequence
            perf_phys = Dataset()
            perf_phys.PersonName = row[11] if row[11] else "Unknown"
            perf_phys.PersonIdentifier = str(row[12]) if row[12] else ""
            sched.ScheduledPerformingPhysicianSequence = [perf_phys]

            ds.ScheduledProcedureStepSequence = [sched]
            responses.append((0xFF00, ds))

        logger.info("Returning %d worklist entries", len(responses))
        return responses
     
def handle_echo(event):
        """Handle C-ECHO requests"""
        logger.info("Received C-ECHO from %s", event.assoc.requestor.ae_title)
        return 0x0000
     
def handle_store(event):
        """Forward C-STORE requests to Orthanc based on the configured connection settings"""
        logger.info("Forwarding C-STORE to Orthanc from %s", event.assoc.requestor.ae_title)
        try:
            # Create a forwarding AE
            forward_ae = AE(ae_title='PYTHON_FORWARDER')
            forward_ae.add_requested_context(event.context.abstract_syntax, event.context.transfer_syntax)
            
            # Connect to Orthanc using the loaded settings
            logger.info("Requesting Association to Orthanc at %s:%s with AE Title %s", ORTHANC_HOST, ORTHANC_PORT, ORTHANC_AET)
            assoc = forward_ae.associate(ORTHANC_HOST, ORTHANC_PORT, ae_title=ORTHANC_AET)
            
            if assoc.is_established:
                # Ensure the dataset has file meta information
                if not hasattr(event.dataset, 'file_meta'):
                    event.dataset.file_meta = Dataset()
                    event.dataset.file_meta.TransferSyntaxUID = event.context.transfer_syntax
                
                status = assoc.send_c_store(event.dataset)
                assoc.release()
                
                if status:
                    logger.info("Forwarded to Orthanc (Status: 0x%04X)", status.Status)
                    return status
                else:
                    logger.error("Orthanc storage failed!")
                    return 0xC001  # Failed - Out of Resources
        except Exception as e:
            logger.exception("Forwarding error: %s", e)
            return 0xC002  # Failed - Unable to process
            
        return 0xC000  # Failed - Unable to understand
     
def main():
        """Start DICOM server with the proper storage support"""
        ae = AE(ae_title="DICOM_MWL_SCU")
        
        # Add supported contexts
        ae.add_supported_context(ModalityWorklistInformationFind)
        ae.add_supported_context(Verification)
        
        storage_classes = [
            SecondaryCaptureImageStorage,
            XRayRadiofluoroscopicImageStorage,
            ComputedRadiographyImageStorage,
            DigitalXRayImageStorageForPresentation,
            XRayAngiographicImageStorage,
            EncapsulatedPDFStorage,
            XRayRadiationDoseSRStorage
        ]
        for cls in storage_classes:
            ae.add_supported_context(cls)
        
        # Set event handlers
        handlers = [
            (evt.EVT_C_FIND, handle_find),
            (evt.EVT_C_ECHO, handle_echo),
            (evt.EVT_C_STORE, handle_store),
        ]
        
        logger.info("Starting DICOM server on port 104...")
        for cls in storage_classes:
            logger.info("- %s", cls.name)
        
        ae.start_server(("0.0.0.0", 104), evt_handlers=handlers)
     
if __name__ == "__main__":
        main()