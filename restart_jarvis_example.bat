@echo off

#Change directory to the location of your JARVIS project
cd /d YOUR_JARVIS_DIRECTORY

call .venv\Scripts\activate

python main.py

pause