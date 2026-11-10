@echo off
rem Snafi worker launcher (copied to C:\SnafiWorker\snafi.cmd). Isolated Python: -I.
"%~dp0venv\Scripts\python.exe" -I "%~dp0app\snafi.py" %*
