# How to Run the Application

This document provides step-by-step instructions on how to run both the FastAPI backend and the Streamlit frontend. You must run these side-by-side in two separate terminal windows.

---

## 1. Starting the Backend Server (Terminal 1)

The backend must be running for the frontend to fetch data.

1. Open a new terminal window (PowerShell).
2. Navigate to the `backend` directory:
   ```powershell
   cd c:\Building_Projects\gridlock\backend
   ```
3. Bypass the execution policy (if blocked on Windows) and activate the virtual environment:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
   ..\venv\Scripts\activate
   ```
4. Start the FastAPI server:
   ```powershell
   uvicorn app.main:app --reload
   ```
5. **Verify:** Open your browser and go to **http://localhost:8000/docs** to see the interactive API documentation.

*(Keep this terminal window open and running!)*

---

## 2. Starting the Frontend Dashboard (Terminal 2)

Leave the first terminal running, and open a **second**, brand new terminal window.

1. Open the new terminal window (PowerShell).
2. Navigate to the `frontend` directory:
   ```powershell
   cd c:\Building_Projects\gridlock\frontend
   ```
3. Bypass the execution policy and activate the virtual environment:
   ```powershell
   Set-ExecutionPolicy -ExecutionPolicy Bypass -Scope Process -Force
   ..\venv\Scripts\activate
   ```
4. Start the Streamlit application:
   ```powershell
   streamlit run app.py
   ```
5. **Verify:** Streamlit will automatically open your default web browser to the dashboard, usually at **http://localhost:8501**.
