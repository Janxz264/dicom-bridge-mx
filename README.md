# dicom-bridge-mx

Python middleware for RIS/HIS interoperability, designed to handle C-ECHO verification, DICOM Worklist SCU, and C-STORE forwarding—built with legacy compatibility and modern extensibility in mind.

---

## 🚀 Features

- **C-ECHO Verification** – Test connectivity with imaging modalities
- **C-FIND Worklist SCU** – Serve scheduled procedure data based on AE Title queries
- **C-STORE Forwarding** – Receive DICOM images and forward to a chosen PACS node
- **Oracle DB Integration** – Dynamic worklist responses powered by customizable SQL
- **JSON-based Configs** – Swap database and destination PACS settings easily
- **Legacy Modality Support** – Compatible with Windows 98–era machines (e.g. AXIOM MULTIX FUSION)

---

## 🔧 System Requirements

See `requirements.txt` for full dependencies. Key modules:

- `pynetdicom`, `pydicom` – DICOM protocol stack
- `cx_Oracle` – Oracle DB access
- `Django`, `djangorestframework` – Optional REST interface
- `Pillow`, `sqlparse`, `tzdata` – Utilities and time zone data

This system runs in production on a Docker container but can be launched via CLI for development purposes.

##  Python version used was 3.11.9

---

## 📂 Configuration Files

### `db_config.json`

Contains Oracle database connection details:

```json
{
  "oracle": {
    "host": "XXXX",
    "port": "XXXX",
    "service_name": "XXXX",
    "username": "XXXX",
    "password": "XXXX"
  }
}
```
💡 Note: You can replace Oracle with any provider—PostgreSQL, MySQL, SQLite—so long as the query logic adapts to your schema.

### `forward_orthanc_connection.json`

Specifies the forwarding destination for DICOM C-STORE requests:

```json
{
  "orthanc": {
    "host": "XXX.XXX.XXX.XXX",
    "port": "XXXX",
    "ae_title": "XXXX"
  }
}
```
🎯 Why this exists: Legacy modalities like the AXIOM MULTIX FUSION DIGITAL WIRELESS FLC, which run on Windows 98, prevent reusing IP addresses across different services (RIS/PACS). This middleware receives studies locally and forwards them to PACS using the config above—effectively decoupling modality UI limitations from the true PACS backend.

Users with newer systems (Windows-based or vendor-embedded OS) may not need this workaround, but it's crucial for maintaining compatibility with functioning legacy hardware.

## 📜 License

This project is licensed under:

🛡️ Creative Commons Attribution-NonCommercial-ShareAlike 4.0 International (CC BY-NC-SA 4.0)

You’re free to use, adapt, and share this code non-commercially with attribution. Commercial use requires explicit permission from the author.

## 🛠️ Running Locally

```python middleware.py```

Logs stream via stdout with configurable verbosity.

## ⚙️ Windows environment setup

Operating System: Windows 10 or later (64-bit recommended)

Python Version: Python 3.11.x (Earlier versions like 3.10 may work, but 3.11 is tested and recommended)

Package Manager: pip (Ensure it's up-to-date with python -m pip install --upgrade pip)

Optional: Use a virtual environment for clean isolation:

```python -m venv ris_env```
```ris_env\Scripts\activate  # Windows```

## 🤝 PACS Compatibility

While ORTHANC was the chosen PACS system here (open source, RESTful), you're free to route studies to any PACS of your choice:

    🔓 Open Source: DCM4CHEE, Orthanc, etc.

    💰 Commercial: MiniPACS, vendor systems

    🛠️ Custom-built: self-hosted services with DICOM SCU/SCP support

Just adjust your forwarding config to match the chosen target.

## ✍️ Author

Built 100% independently by me assisted only by AI tools.

> *Built to bridge systems that weren’t meant to talk—but absolutely need to.*