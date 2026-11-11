@echo off
rem Snafi worker launcher (copied to C:\SnafiWorker\snafi.cmd). The worker's own private Python, isolated (-I).
"%~dp0python\tools\python.exe" -I "%~dp0app\snafi.py" %*
