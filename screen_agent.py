"""
Screen Agent - AI-powered desktop automation using Ollama vision models.
Controls your screen, mouse, and keyboard via natural language commands.
"""

import customtkinter as ctk
import pyautogui
import mss
import mss.tools
import ollama
import json
import threading
import time
import base64
import io
import re
import subprocess
import sys
import math
import os
from PIL import Image, ImageDraw, ImageFont, ImageTk
from datetime import datetime

# Toolkit integration
try:
    from toolkit.registry import get_registry
    TOOLKIT_AVAILABLE = True
except ImportError:
    TOOLKIT_AVAILABLE = False

# Safety: prevent pyautogui from moving too fast / allow emergency stop
pyautogui.PAUSE = 0.3
pyautogui.FAILSAFE = True  # Move mouse to top-left corner to abort

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
SAVED_TASKS_FILE = os.path.join(DATA_DIR, "saved_tasks.json")
HISTORY_FILE = os.path.join(DATA_DIR, "history.json")

os.makedirs(DATA_DIR, exist_ok=True)

SYSTEM_PROMPT = """You are a computer automation agent. Respond with exactly ONE JSON action per turn.

PRIORITY ORDER — always prefer the method higher on this list:
1. tool_call with toolkit functions (system_monitor, process_manager, text_processing, etc.) — for system tasks, file ops, data, network, etc.
2. tool_call with browser_control.cdp_* — for controlling web pages by CSS selector (NO coordinate guessing)
3. tool_call with window_control.win_* — for controlling desktop apps by element name (NO coordinate guessing)
4. click/type/key — LAST RESORT only if no tool_call can do it

BROWSER TASKS — use browser_control (exact CSS selectors, not pixel coordinates):
{{"action":"tool_call","tool":"browser_control.cdp_connect_tab","args":{{"url_pattern":"google"}},"reason":"connect to Google tab"}}
{{"action":"tool_call","tool":"browser_control.cdp_get_form_fields","args":{{}},"reason":"inspect form inputs"}}
{{"action":"tool_call","tool":"browser_control.cdp_type","args":{{"selector":"input[name=q]","text":"hello"}},"reason":"type in search"}}
{{"action":"tool_call","tool":"browser_control.cdp_click","args":{{"selector":"#search-button"}},"reason":"click search"}}
{{"action":"tool_call","tool":"browser_control.cdp_get_page_text","args":{{}},"reason":"read page content"}}

DESKTOP APP TASKS — use window_control (exact element names, not coordinates):
{{"action":"tool_call","tool":"window_control.win_list_windows","args":{{}},"reason":"see open windows"}}
{{"action":"tool_call","tool":"window_control.win_get_controls","args":{{"title":"Notepad"}},"reason":"list controls"}}
{{"action":"tool_call","tool":"window_control.win_click_button","args":{{"title":"Notepad","button_name":"Save"}},"reason":"click save"}}
{{"action":"tool_call","tool":"window_control.win_type_in_field","args":{{"title":"Notepad","text":"hello"}},"reason":"type text"}}

SYSTEM/FILE TASKS — use toolkit functions:
{{"action":"tool_call","tool":"system_monitor.get_cpu_usage","args":{{}},"reason":"check CPU"}}
{{"action":"tool_call","tool":"process_manager.run_command","args":{{"command":"dir"}},"reason":"list files"}}

OTHER ACTIONS:
{{"action":"think","thought":"planning...","reason":"deciding next step"}}
{{"action":"done","reason":"task complete"}}
{{"action":"click","x":500,"y":300,"button":"left","reason":"last resort click"}}
{{"action":"type","text":"hello","reason":"typing"}}
{{"action":"key","key":"enter","reason":"pressing key"}}

For UI tasks: FIRST inspect (cdp_get_form_fields or win_get_controls), THEN act on what you find.

Toolkit: {tools}
Screen: {width}x{height}. Reply with ONE valid JSON object. No markdown, no code fences.
"""

# ── Automation Workflows ─────────────────────────────────────────────────────
# Each automation: (name, description, category, steps_estimate, prompt, needs_input)
AUTOMATIONS = [
    # ═══════════════════════════════════════════════════════════════════
    # LONG AUTOMATIONS - these run many steps and do real work
    # ═══════════════════════════════════════════════════════════════════

    ("Full System Health Check",
     "Runs a complete diagnostic of your computer. Checks CPU usage, memory, disk space, running processes, network status, battery health, and system uptime. Gives you a full report of everything.",
     "Long Automation", "~15 steps",
     "Perform a comprehensive system health check. Use toolkit functions to: 1) Get CPU usage and info with system_monitor.get_cpu_usage and system_monitor.get_cpu_info, 2) Check memory with system_monitor.get_memory_usage, 3) Check disk space with system_monitor.get_disk_usage, 4) Get all disk info with system_monitor.get_all_disks, 5) List the top processes by CPU with system_monitor.get_process_list, 6) Check network interfaces with system_monitor.get_network_interfaces, 7) Get battery status with system_monitor.get_battery_status, 8) Get system uptime with system_monitor.get_system_uptime, 9) Get OS info with system_monitor.get_os_info. After gathering all data, use think to write a clear summary report of the system health in plain English, noting any concerns.", False),

    ("Organize My Downloads Folder",
     "Goes through your entire Downloads folder and sorts files into subfolders by type. Creates folders like Images, Documents, Videos, Music, Archives, Installers, and Other. Moves every file to the right place. This can take a while if you have lots of files.",
     "Long Automation", "~20 steps",
     "Organize the user's Downloads folder. Step by step: 1) First use process_manager.run_command to list all files in the Downloads folder with 'dir /b C:\\Users\\computer\\Downloads'. 2) Think about what categories to create based on file extensions found. 3) Create subfolders: Images, Documents, Videos, Music, Archives, Installers, Code, Other using process_manager.run_command with 'mkdir' for each. 4) Move files by extension: .jpg/.png/.gif/.bmp/.svg/.webp -> Images, .pdf/.doc/.docx/.txt/.xlsx/.csv/.pptx -> Documents, .mp4/.avi/.mkv/.mov/.wmv -> Videos, .mp3/.wav/.flac/.aac -> Music, .zip/.rar/.7z/.tar/.gz -> Archives, .exe/.msi/.bat -> Installers, .py/.js/.html/.css/.java/.cpp -> Code, everything else -> Other. Use process_manager.run_command with 'move' commands. 5) After moving, report how many files were sorted into each category.", False),

    ("Deep Clean Temp Files",
     "Finds and removes temporary files, cache data, and other junk that's wasting space on your computer. Checks Windows temp folders, browser caches, and old log files. Shows you how much space was recovered.",
     "Long Automation", "~12 steps",
     "Clean up temporary files to free disk space. Steps: 1) Use process_manager.run_command to check size of temp folders: 'dir /s C:\\Users\\computer\\AppData\\Local\\Temp' and 'dir /s C:\\Windows\\Temp'. 2) Think about what can safely be deleted. 3) Use process_manager.run_command to delete temp files: 'del /q /s C:\\Users\\computer\\AppData\\Local\\Temp\\*' and similar for Windows Temp. 4) Check Recycle Bin size. 5) Look for large .log files in common locations. 6) Report total space freed and what was cleaned.", False),

    ("Watch My Computer's Performance",
     "Monitors your CPU, memory, and disk usage over 60 seconds, taking a measurement every 5 seconds. At the end, tells you if anything is running too high and which programs are using the most resources. Great for finding what's slowing your PC down.",
     "Long Automation", "~15 steps",
     "Monitor system performance over time. Take 12 measurements, 5 seconds apart: 1) Use system_monitor.get_cpu_usage to measure CPU. 2) Use system_monitor.get_memory_usage to measure RAM. 3) Wait 5 seconds. 4) Repeat steps 1-3 twelve times total. 5) After all measurements, use system_monitor.get_process_list sorted by cpu_percent to find the top resource hogs. 6) Use think to write a performance report: average CPU, peak CPU, memory trend, and which processes are consuming the most. Flag anything over 80% as a concern.", False),

    ("Batch Rename Files",
     "Renames a bunch of files in a folder all at once. You tell it the folder and the naming pattern you want (like adding a prefix, changing extensions, or numbering them). Saves hours of manual renaming.",
     "Long Automation", "~10 steps",
     "Batch rename files in a folder. First ask the user what folder and naming pattern they want by using think to explain: 'I need to know: 1) Which folder contains the files? 2) What naming pattern? Examples: add prefix like \"vacation_\", add numbers like \"photo_001\", change extension from .jpeg to .jpg'. Then wait for the user to provide details via the task. Use process_manager.run_command with 'ren' or 'move' commands to rename each file. Report results when done.", False),

    ("Research a Topic",
     "Acts like a research assistant. Give it a topic and it will search the web, read through results, take notes, and write you a summary with key findings. Great for learning about something new or gathering info for a project.",
     "Long Automation", "~20 steps",
     "Research the following topic thoroughly: {query}. Steps: 1) Open the web browser by pressing the Windows key, typing 'chrome' or the default browser, and pressing Enter. 2) Navigate to google.com. 3) Search for the topic. 4) Read the search results page - use think to note the top 5 results and what they cover. 5) Click on the most relevant result. 6) Scroll through and read the page content. 7) Use think to take detailed notes on key facts, dates, names, and concepts. 8) Go back and visit 2-3 more sources. 9) Use think to compile a comprehensive summary with: Overview, Key Facts, Important Details, and Sources visited.", True),

    # ═══════════════════════════════════════════════════════════════════
    # SYSTEM INFO - learn about your computer
    # ═══════════════════════════════════════════════════════════════════

    ("What's Using My CPU?",
     "Shows you exactly which programs are eating up your processor right now. Lists the top resource hogs so you can decide what to close.",
     "System Info", "~3 steps",
     "Check what's consuming CPU resources. Use system_monitor.get_process_list with sort_by='cpu_percent' to get all running processes sorted by CPU usage. Then use think to list the top 10 processes in a clear table format with their name, CPU %, and memory %, highlighting anything using more than 10% CPU.", False),

    ("How Much Storage Do I Have?",
     "Checks all your drives and tells you how much space is used, how much is free, and warns you if anything is getting full.",
     "System Info", "~3 steps",
     "Check disk storage on all drives. Use system_monitor.get_all_disks to list partitions, then use system_monitor.get_disk_usage for each mountpoint. Use think to present results in a clear format: Drive letter, Total size (GB), Used (GB), Free (GB), % full. Warn if any drive is over 85% full.", False),

    ("What's My Computer's Specs?",
     "Gets your full computer specifications - processor, RAM, OS version, screen resolution, and more. Useful for system requirements checks or tech support.",
     "System Info", "~5 steps",
     "Gather complete system specifications. Use: 1) system_monitor.get_os_info for OS details, 2) system_monitor.get_cpu_info for processor, 3) system_monitor.get_cpu_count for core count, 4) system_monitor.get_memory_usage for RAM total, 5) system_monitor.get_hostname for computer name. Use think to present a clean spec sheet.", False),

    ("Check Battery Health",
     "For laptops - shows your current battery level, whether it's charging, estimated time remaining, and overall battery condition.",
     "System Info", "~2 steps",
     "Check battery status. Use system_monitor.get_battery_status to get battery info. Use think to explain: current charge %, plugged in or not, estimated time remaining, and any health concerns.", False),

    ("Network Status Report",
     "Shows all your network connections, IP addresses, and which programs are using the internet. Helps troubleshoot connectivity issues.",
     "System Info", "~4 steps",
     "Generate a network status report. Use: 1) system_monitor.get_network_interfaces to list all adapters and IPs, 2) system_monitor.get_network_io for traffic stats, 3) system_monitor.get_ip_addresses for IP summary. Use think to present: connected networks, IP addresses, upload/download totals, and connection health.", False),

    # ═══════════════════════════════════════════════════════════════════
    # FILE MANAGEMENT - organize and work with files
    # ═══════════════════════════════════════════════════════════════════

    ("Find Large Files",
     "Scans a folder for files over 100MB. Helps you find what's eating up your disk space so you can delete or move the big ones.",
     "File Management", "~3 steps",
     "Find large files consuming disk space. Use process_manager.run_command to run: 'forfiles /P C:\\ /S /M *.* /C \"cmd /c if @fsize GEQ 104857600 echo @path @fsize\" 2>nul' to find files over 100MB. Use think to list them sorted by size with human-readable sizes (MB/GB).", False),

    ("Create Project Folder Structure",
     "Sets up a complete project folder with organized subfolders. Creates folders for docs, source code, assets, tests, and more. Just give it a project name.",
     "File Management", "~5 steps",
     "Create a well-organized project folder structure for: {query}. Use process_manager.run_command to create: 1) Main project folder on Desktop, 2) Subfolders: docs, src, assets, tests, config, build, notes. 3) Create a README.txt in the main folder with the project name and date. Report the full structure when done.", True),

    ("List Everything Running",
     "Shows every program and process currently running on your computer with details about memory and CPU usage.",
     "File Management", "~2 steps",
     "List all running processes. Use system_monitor.get_process_list with sort_by='memory_percent'. Use think to present the top 20 in a readable table: Name, PID, CPU%, Memory%, Status.", False),

    # ═══════════════════════════════════════════════════════════════════
    # SECURITY - passwords and safety
    # ═══════════════════════════════════════════════════════════════════

    ("Generate Strong Passwords",
     "Creates 5 unique, strong passwords for you. Each one is long, random, and includes uppercase, lowercase, numbers, and symbols. Copy whichever one you like best.",
     "Security", "~5 steps",
     "Generate 5 strong passwords. Use encryption_actions.generate_password with length=16, uppercase=True, lowercase=True, digits=True, special=True - call it 5 times with different lengths (12, 16, 20, 24, 32). Use think to present all 5 passwords clearly numbered, with a note about which length is best for what purpose.", False),

    ("Check File Integrity",
     "Calculates the SHA-256 hash of a file. Use this to verify a download is legitimate or hasn't been tampered with. Give it a file path.",
     "Security", "~2 steps",
     "Calculate the SHA-256 hash of the file at: {query}. Use encryption_actions.hash_file with the file path and algorithm='sha256'. Use think to show the hash and explain what it means and how to use it for verification.", True),

    ("Generate a Secure Token",
     "Creates a cryptographically secure random token. Useful for API keys, session tokens, or any time you need a secure random string.",
     "Security", "~2 steps",
     "Generate secure tokens. Use encryption_actions.generate_token with length=32, then encryption_actions.generate_api_key with prefix='sk_', and encryption_actions.generate_uuid for a UUID. Use think to present all three with labels explaining what each is best used for.", False),

    # ═══════════════════════════════════════════════════════════════════
    # PRODUCTIVITY - get work done
    # ═══════════════════════════════════════════════════════════════════

    ("What Time Is It Everywhere?",
     "Shows the current time in major cities around the world. Useful for scheduling calls across time zones.",
     "Productivity", "~3 steps",
     "Get current time in multiple timezones. Use date_time_actions.get_current_time for each: UTC, America/New_York, America/Los_Angeles, Europe/London, Europe/Berlin, Asia/Tokyo, Asia/Shanghai, Australia/Sydney. Use think to present a clean world clock display.", False),

    ("Create a Daily Log",
     "Opens Notepad and creates a formatted daily log template with today's date, sections for tasks, notes, and accomplishments. Ready for you to fill in.",
     "Productivity", "~5 steps",
     "Create a daily log. First use date_time_actions.get_current_date to get today's date. Then open Notepad by pressing Windows key, typing 'notepad', pressing Enter. Type a formatted daily log template with: the date as header, sections for 'Today\\'s Goals', 'Tasks Completed', 'Notes', 'Tomorrow\\'s Plan', with bullet points and spacing.", False),

    ("Draft an Email",
     "Helps you compose a professional email. Tell it who it's to and what about, and it'll open your email and start drafting.",
     "Productivity", "~8 steps",
     "Help compose an email about: {query}. Open the web browser, go to gmail.com (or the email client visible on screen). Click Compose. Use think to draft a professional email based on the topic, then type it out in the compose window.", True),

    ("Open App",
     "Opens any application on your computer. Just tell it the name - Chrome, Notepad, Calculator, File Explorer, anything.",
     "Productivity", "~2 steps",
     "Open the application: {query}. Press the Windows key, type the app name, wait a moment for results, then press Enter to launch it.", True),

    # ═══════════════════════════════════════════════════════════════════
    # DATA & TEXT - process information
    # ═══════════════════════════════════════════════════════════════════

    ("Process Text from Clipboard",
     "Reads whatever text is on your clipboard and processes it - can count words, extract emails/URLs/phone numbers, or clean up formatting. Tell it what you need.",
     "Data & Text", "~4 steps",
     "Process the text currently on the clipboard. Use clipboard_advanced.paste_text to read clipboard content. Then use text_processing.word_count, text_processing.extract_emails, text_processing.extract_urls, and text_processing.extract_phone_numbers on the text. Use think to present a summary: word count, character count, any emails/URLs/phones found, and first 200 chars of the text.", False),

    ("Find & Replace in Clipboard",
     "Takes text from your clipboard, finds a pattern, replaces it with something else, and puts the result back. Great for bulk text edits.",
     "Data & Text", "~3 steps",
     "Find and replace text in clipboard. First use clipboard_advanced.paste_text to get current clipboard content. Then ask via think: 'What should I find and what should I replace it with? The clipboard currently contains [first 100 chars]...' Wait for user direction in the task.", False),

    ("Generate a Password List",
     "Creates a list of 10 strong, unique passwords with different lengths and styles. Copies the full list to your clipboard so you can paste it anywhere.",
     "Data & Text", "~6 steps",
     "Generate 10 unique passwords and copy to clipboard. Use encryption_actions.generate_password with varying settings: 1) 12 chars standard, 2) 16 chars standard, 3) 20 chars standard, 4) 24 chars extra strong, 5) 12 chars no special chars, 6) 8 chars simple, 7-10) 16 chars standard. After generating all 10, combine them into a numbered list and use clipboard_advanced.copy_text to put the list on the clipboard. Use think to confirm it's been copied.", False),

    # ═══════════════════════════════════════════════════════════════════
    # SCREEN & VISUAL - see and interact with what's on screen
    # ═══════════════════════════════════════════════════════════════════

    ("Describe My Screen",
     "Takes a careful look at everything visible on your screen and describes it in detail. Lists every window, icon, notification, and text it can see. Useful for troubleshooting or accessibility.",
     "Screen & Visual", "~2 steps",
     "Carefully analyze the entire screen. Describe every window, icon, taskbar item, and notification you can see. List them in order from top to bottom, left to right. Note the active window, any error messages, system tray icons, and the time. Use the think action to give a comprehensive description.", False),

    ("Debug This Error",
     "Reads any error message, dialog box, or warning on your screen and explains what it means in plain English. Then suggests how to fix it.",
     "Screen & Visual", "~3 steps",
     "Look at the screen for any error messages, dialog boxes, or warnings. Read every word of the error carefully. Use think to: 1) Quote the exact error text, 2) Explain what this error means in simple terms, 3) List 3-5 possible causes, 4) Give step-by-step instructions to fix each cause, starting with the most likely.", False),

    ("Take a Screenshot",
     "Captures your entire screen and saves it as an image file. Uses the built-in screenshot tool.",
     "Screen & Visual", "~2 steps",
     "Take a screenshot. Press Windows+Shift+S to open the snipping tool, then click 'Full Screen Snip' or press the fullscreen mode button to capture the entire screen.", False),

    ("Read This Page To Me",
     "Scrolls through whatever page or document is on screen and reads all the content. Then gives you a bullet-point summary of the key information.",
     "Screen & Visual", "~6 steps",
     "Read and summarize the content on screen. Steps: 1) Look at the current screen and use think to note what application/page is open. 2) Read all visible text. 3) Scroll down slowly. 4) Read the next section. 5) Continue scrolling and reading until you reach the bottom. 6) Use think to write a comprehensive summary with bullet points covering all key information found.", False),

    # ═══════════════════════════════════════════════════════════════════
    # QUICK ACTIONS - fast one-step tasks
    # ═══════════════════════════════════════════════════════════════════

    ("Copy All Text",
     "Selects everything in the current window and copies it to your clipboard. Works in any text field, document, or web page.",
     "Quick Actions", "~1 step",
     "Press Ctrl+A to select all text in the current window, then press Ctrl+C to copy it to the clipboard.", False),

    ("Minimize Everything",
     "Instantly minimizes all open windows to show your desktop. Press it again to restore them.",
     "Quick Actions", "~1 step",
     "Press Windows+D to show the desktop by minimizing all windows.", False),

    ("Close This Window",
     "Closes whatever window is currently active and in focus.",
     "Quick Actions", "~1 step",
     "Press Alt+F4 to close the currently focused window.", False),

    ("Open Task Manager",
     "Opens Windows Task Manager so you can see running processes, performance, and manage apps.",
     "Quick Actions", "~1 step",
     "Press Ctrl+Shift+Escape to open Task Manager.", False),

    ("Open Settings",
     "Opens the Windows Settings app where you can configure your system, display, network, and more.",
     "Quick Actions", "~1 step",
     "Press Windows+I to open Windows Settings.", False),

    ("Mute / Unmute",
     "Toggles your system audio on or off.",
     "Quick Actions", "~1 step",
     "Press the Volume Mute key to toggle system audio mute.", False),

    ("Volume Up",
     "Turns the system volume up a few notches.",
     "Quick Actions", "~1 step",
     "Press the Volume Up key 5 times to increase the system volume.", False),

    ("Volume Down",
     "Turns the system volume down a few notches.",
     "Quick Actions", "~1 step",
     "Press the Volume Down key 5 times to decrease the system volume.", False),

    ("New Browser Tab",
     "Opens a new empty tab in your web browser.",
     "Quick Actions", "~1 step",
     "Press Ctrl+T to open a new tab in the current browser.", False),

    ("Search the Web",
     "Opens your browser and searches Google for whatever you type. Just enter your search query.",
     "Quick Actions", "~3 steps",
     "Open the default web browser, go to google.com, and search for: {query}", True),

    ("Click a Button",
     "Finds and clicks a specific button, link, or UI element on screen. Tell it what to look for.",
     "Quick Actions", "~2 steps",
     "Look at the screen and find a button or link labeled '{query}'. Click on it.", True),

    # ═══════════════════════════════════════════════════════════════════
    # SCREEN POWER - OCR, templates, color analysis
    # ═══════════════════════════════════════════════════════════════════

    ("Read Text from Screen (OCR)",
     "Uses OCR to extract all readable text from your screen or a region of it. Great for copying text from images, PDFs, or apps that don't let you select text.",
     "Screen Power", "~3 steps",
     "Use screen_ocr_extractor to capture and extract text from the current screen. First use ScreenOCR to take a screenshot, preprocess it for clarity, then run OCR to extract all visible text. Use think to present the extracted text cleanly. If possible, use clipboard_advanced.copy_text to put it on the clipboard.", False),

    ("Pick Colors from Screen",
     "Analyzes the colors on your screen. Shows you the dominant colors, their hex codes, and RGB values. Perfect for designers or picking colors from any app.",
     "Screen Power", "~3 steps",
     "Use screen_color_analyzer to analyze colors on the current screen. Capture a screenshot, identify the dominant colors, and present them with hex codes and RGB values. Use think to show a color palette with each color's hex code, RGB, and what percentage of the screen it covers.", False),

    ("Find Something on Screen",
     "Searches your screen for a specific visual element - a button, icon, or image. Tells you exactly where it is. Useful for automation and accessibility.",
     "Screen Power", "~3 steps",
     "Use screen_template_matcher to search the screen for: {query}. Capture the current screen, attempt to locate the visual element matching the description. Report its coordinates and size if found.", True),

    ("Batch OCR - Read Text from Images",
     "Reads text from multiple image files at once. Point it at a folder of screenshots or photos and it extracts all the text from each one.",
     "Screen Power", "~8 steps",
     "Use screen_ocr_batch.BatchOCRProcessor to process all images in: {query}. Scan the folder for .png, .jpg, .jpeg, .bmp files. Run OCR on each image. Compile all extracted text and present it organized by filename. Report total images processed and text found.", True),

    # ═══════════════════════════════════════════════════════════════════
    # CLEANUP & ORGANIZE - smart file and system management
    # ═══════════════════════════════════════════════════════════════════

    ("Smart System Cleanup",
     "Deep cleans your system by scanning temp files, browser caches, old logs, and Windows update leftovers. Shows you what it found and how much space you can save before deleting anything.",
     "Cleanup & Organize", "~10 steps",
     "Use auto_system_cleaner.SystemCleaner to perform a comprehensive system cleanup. Steps: 1) Scan Windows temp folder, 2) Scan user temp folder, 3) Scan browser caches (Chrome, Firefox, Edge), 4) Scan Windows update cleanup files, 5) Find old log files. Present a summary of what was found and total space that can be recovered. Only delete after confirming with think what will be removed.", False),

    ("Sort Files by Type",
     "Looks at a folder and organizes every file into neat subfolders based on file type - Images, Documents, Videos, Music, Archives, Code, and more. Handles hundreds of files.",
     "Cleanup & Organize", "~12 steps",
     "Use auto_file_organizer.FileOrganizer to sort all files in the Downloads folder (C:\\Users\\computer\\Downloads) into subfolders by type. Create rules for: Images (.jpg,.png,.gif,.bmp,.svg,.webp), Documents (.pdf,.doc,.docx,.txt,.xlsx,.csv,.pptx), Videos (.mp4,.avi,.mkv,.mov), Music (.mp3,.wav,.flac,.aac), Archives (.zip,.rar,.7z,.tar,.gz), Code (.py,.js,.html,.css,.java,.cpp), Installers (.exe,.msi,.bat). Apply the rules and report how many files were moved to each category.", False),

    ("Smart Rename Files",
     "Renames files in bulk using patterns. Add prefixes, suffixes, sequential numbers, dates, or use regex find-and-replace across many files at once.",
     "Cleanup & Organize", "~8 steps",
     "Use auto_file_renamer.FileRenamer to batch rename files. Ask the user via think: 'Which folder should I rename files in? What pattern? Options: 1) Add prefix like photo_, 2) Add date prefix like 2026-04-02_, 3) Sequential numbers like file_001, 4) Find and replace text in names, 5) Change extensions'. Then apply the chosen rename pattern and report results.", False),

    ("Organize Screenshots",
     "Finds all your screenshots and organizes them into folders by date (Year/Month). Also renames them with readable names instead of random numbers.",
     "Cleanup & Organize", "~10 steps",
     "Use auto_screenshot_organizer to find and organize screenshots. Scan common screenshot locations: Desktop, Downloads, Pictures/Screenshots. Sort them into Year/Month subfolders. Rename with readable date-based names. Report total screenshots found and organized.", False),

    # ═══════════════════════════════════════════════════════════════════
    # AUTOMATION POWER - macros, workflows, data entry
    # ═══════════════════════════════════════════════════════════════════

    ("Record a Macro",
     "Records your mouse clicks and keyboard presses, then saves them so you can replay the exact sequence later. Like a personal robot that learns from watching you.",
     "Automation Power", "~5 steps",
     "Use screen_macro_recorder.MacroRecorder to start recording user actions. Explain via think: 'I will record your mouse clicks and key presses for 30 seconds. Do your task normally and I will save the macro for replay later. Starting recording now...' Record for 30 seconds, then save the macro and report what was captured.", False),

    ("Play a Saved Macro",
     "Replays a previously recorded macro - repeating the exact mouse clicks and keyboard presses you recorded earlier.",
     "Automation Power", "~3 steps",
     "Use screen_macro_recorder.MacroPlayer to replay a saved macro. List available macros, let the user pick one, then play it back at the original speed.", False),

    ("Auto Fill Forms",
     "Automatically fills in form fields on screen using data you provide. Great for repetitive data entry across multiple forms or web pages.",
     "Automation Power", "~8 steps",
     "Use auto_data_entry.DataEntryAutomator to automatically fill form fields on screen. First detect form fields visible on the current screen using FormDetector. Then ask via think what data to fill in each field. Tab between fields and type the values. Report how many fields were filled.", False),

    ("Multi-Step Workflow",
     "Runs a chain of automated steps one after another. Each step can be a different action - click here, type there, wait, check something, repeat. Build your own automation.",
     "Automation Power", "~15 steps",
     "Use desktop_task_automator.WorkflowEngine to build and run a multi-step workflow. Ask the user via think: 'Describe the steps you want automated. Example: 1) Open Chrome, 2) Go to a website, 3) Click login, 4) Type username, 5) Type password, 6) Click submit'. Build the workflow from their description and execute it step by step, reporting progress.", False),

    # ═══════════════════════════════════════════════════════════════════
    # WINDOW & AUDIO - desktop environment control
    # ═══════════════════════════════════════════════════════════════════

    ("Arrange Windows Side by Side",
     "Snaps your open windows into a neat layout - side by side, stacked, or grid. Pick a layout and all your windows rearrange automatically.",
     "Window & Audio", "~4 steps",
     "Use auto_window_resizer to arrange open windows. Get the list of visible windows, then arrange them side-by-side (2 windows: left/right halves) or in a grid (3-4 windows: quadrants). Use pyautogui hotkeys: Win+Left, Win+Right for snapping. Report the final layout.", False),

    ("Control Volume",
     "Set your system volume to an exact level, mute/unmute, or adjust it up and down. Works even if you can't find the volume controls.",
     "Window & Audio", "~2 steps",
     "Use auto_sound_controller to control system audio. Ask the user via think what they want: 'What volume level? Options: 1) Set to specific % (0-100), 2) Mute, 3) Unmute, 4) Increase by 10%, 5) Decrease by 10%'. Then apply the audio change.", False),

    ("Clipboard History Search",
     "Shows you everything you've copied recently and lets you search through your clipboard history. Find that text you copied hours ago.",
     "Window & Audio", "~3 steps",
     "Use clipboard_history_manager.ClipboardHistoryManager to display clipboard history. Show the last 20 items copied to clipboard with timestamps. If the user provides a search term, filter the history to matching items. Present results clearly.", False),
]

# Category styling
CAT_COLORS = {
    "Long Automation": "#f59e0b",
    "System Info": "#10b981",
    "File Management": "#3b82f6",
    "Security": "#ef4444",
    "Productivity": "#8b5cf6",
    "Data & Text": "#06b6d4",
    "Screen & Visual": "#ec4899",
    "Quick Actions": "#64748b",
    "Screen Power": "#a855f7",
    "Cleanup & Organize": "#14b8a6",
    "Automation Power": "#f97316",
    "Window & Audio": "#0ea5e9",
}

CAT_ICONS = {
    "Long Automation": "These run many steps automatically. Sit back and watch.",
    "System Info": "Learn about your computer's health and specs.",
    "File Management": "Organize, find, and manage your files.",
    "Security": "Passwords, encryption, and safety tools.",
    "Productivity": "Get work done faster.",
    "Data & Text": "Process, transform, and analyze text and data.",
    "Screen & Visual": "See, read, and interact with what's on screen.",
    "Quick Actions": "Simple one-click shortcuts.",
    "Screen Power": "OCR text reading, color analysis, and visual search.",
    "Cleanup & Organize": "Smart file sorting, renaming, and system cleanup.",
    "Automation Power": "Record macros, auto-fill forms, and build workflows.",
    "Window & Audio": "Control windows, volume, and clipboard history.",
}

# ── Category Info for Tools Tab ─────────────────────────────────────────────
# Maps all 22 registry categories to beginner-friendly info for the Tools tab.
CATEGORY_INFO = {
    "System": {
        "color": "#10b981",
        "icon": "System",
        "desc": "Think of this like a dashboard for your computer. These functions let you peek under the hood — see how hard your processor is working, how much memory is being used, what programs are running, whether your battery is healthy, and much more. You don't need to open Task Manager ever again.",
        "example": "Give me a full system health report including CPU, memory, and battery",
        "bullets": ["Check CPU usage and temperature in real time", "See how much RAM is free vs in use", "List every program currently running", "Check battery level, charge status, and health", "View system uptime, OS version, and specs"],
    },
    "Network": {
        "color": "#3b82f6",
        "icon": "Network",
        "desc": "Everything related to your internet and network connections. These functions can show you your IP address, check if a website is reachable, scan for open ports, measure your network speed, and troubleshoot connection problems — all without opening a browser or command prompt.",
        "example": "Show me my IP address and all active network connections",
        "bullets": ["Get your public and local IP addresses", "Ping websites to check if they're online", "Scan for open ports on a computer", "Check network adapter info and traffic stats", "Resolve domain names to IP addresses"],
    },
    "Files": {
        "color": "#f59e0b",
        "icon": "Files",
        "desc": "Everything you can do with files and folders. Copy, move, delete, rename, search — these functions handle it all without you needing to click through File Explorer. Great for moving hundreds of files at once or finding something buried deep in your drives.",
        "example": "Find all files larger than 100MB and show me where they are",
        "bullets": ["Copy, move, rename, and delete files", "Create and remove entire folder trees", "Search for files by name, size, or date", "Read and write text files", "Watch a folder for new or changed files"],
    },
    "Data": {
        "color": "#2563eb",
        "icon": "Data",
        "desc": "Tools for storing and retrieving information. Imagine a super-fast sticky note system built into your computer — you can save any piece of data with a label, get it back instantly, and it remembers it even after a restart. Also includes tools for working with databases and structured data.",
        "example": "Store my API key in cache and retrieve it later",
        "bullets": ["Save data in memory for fast access (cache)", "Persist data to disk across restarts", "Read and write JSON, CSV, and other data files", "Query and update SQLite databases", "Export and import data between formats"],
    },
    "Text": {
        "color": "#06b6d4",
        "icon": "Text",
        "desc": "Everything you could want to do with text. Count words, find and replace patterns, extract emails and phone numbers, check spelling, convert between formats, compare two documents — if it involves words and characters, there's a function here for it.",
        "example": "Extract all email addresses and phone numbers from my clipboard",
        "bullets": ["Count words, characters, sentences, and paragraphs", "Find and replace with powerful search patterns", "Extract emails, URLs, and phone numbers from text", "Convert text case (UPPER, lower, Title, camelCase)", "Compare two pieces of text and highlight differences"],
    },
    "Screen": {
        "color": "#ec4899",
        "icon": "Screen",
        "desc": "Functions that work with what's on your screen. Take screenshots, read text from images using OCR (optical character recognition), find buttons and elements by looking for them visually, analyze colors, and record everything that happens on screen.",
        "example": "Read all the text currently visible on my screen",
        "bullets": ["Take screenshots of the whole screen or regions", "Read text from screen with OCR (even from images)", "Find and locate specific buttons or icons visually", "Analyze colors on screen and get hex codes", "Record screen activity as video"],
    },
    "Image": {
        "color": "#a855f7",
        "icon": "Image",
        "desc": "Edit and transform image files. Resize photos before sending them, crop out unwanted parts, apply filters like blur or sharpen, add watermarks, convert between formats (.jpg to .png, etc.), and create thumbnails. Works on single images or entire folders at once.",
        "example": "Resize all images in my Downloads folder to 800x600",
        "bullets": ["Resize images to exact dimensions or percentages", "Crop, rotate, and flip images", "Apply filters: blur, sharpen, brightness, contrast", "Convert between PNG, JPG, BMP, WEBP formats", "Add watermarks, text overlays, and borders"],
    },
    "Audio": {
        "color": "#f97316",
        "icon": "Audio",
        "desc": "Control sound on your computer. Adjust the system volume, mute and unmute, change what audio device is active, and work with audio files. Also includes text-to-speech — the computer can read text out loud for you.",
        "example": "Set my system volume to 50% and check what audio devices I have",
        "bullets": ["Get and set system volume level (0–100%)", "Mute and unmute system audio", "List available audio input and output devices", "Convert audio files between formats", "Have the computer read text aloud (text-to-speech)"],
    },
    "DevTools": {
        "color": "#64748b",
        "icon": "DevTools",
        "desc": "Tools aimed at developers and power users. Run code snippets, check code quality, generate UUIDs and tokens, format JSON and XML, encode and decode data, and more. If you write code or work with technical data, this category is very useful.",
        "example": "Generate a UUID and format this JSON data cleanly",
        "bullets": ["Generate UUIDs, API keys, and random tokens", "Format and validate JSON and XML data", "Encode and decode Base64 and URL data", "Run Python code snippets safely", "Calculate checksums and hashes"],
    },
    "Security": {
        "color": "#ef4444",
        "icon": "Security",
        "desc": "Stay safe and secure. These tools generate strong passwords that are nearly impossible to guess, verify files haven't been tampered with (using hashes), encrypt sensitive text so nobody else can read it, and help you manage secrets safely. No security knowledge required.",
        "example": "Generate 5 strong passwords of different lengths",
        "bullets": ["Generate strong random passwords (any length)", "Hash files and text with MD5, SHA-256, SHA-512", "Verify a file's integrity hasn't been changed", "Base64 encode/decode for safe data transmission", "Generate secure tokens, API keys, and UUIDs"],
    },
    "Automation": {
        "color": "#7c3aed",
        "icon": "Automation",
        "desc": "Build your own automated workflows. Chain multiple actions together into a sequence that runs automatically. Like writing a recipe for your computer to follow: first do this, then check that, then do this other thing. Supports conditions, loops, and parallel steps.",
        "example": "Create a workflow that checks disk space and cleans temp files if over 80% full",
        "bullets": ["Build multi-step automated workflows", "Add conditions: do X only if Y is true", "Run steps in parallel for speed", "Pause, resume, and cancel running workflows", "Save and reuse workflow templates"],
    },
    "DateTime": {
        "color": "#14b8a6",
        "icon": "DateTime",
        "desc": "Everything related to dates and times. Find out what time it is anywhere in the world right now, calculate how many days until an event, convert between timezones, check if a date falls on a holiday, and format dates however you need them.",
        "example": "What time is it right now in Tokyo, New York, London, and Sydney?",
        "bullets": ["Get current time in any timezone worldwide", "Calculate days/hours between two dates", "Convert dates between different formats", "Check if a date is a weekend or public holiday", "Get the current week number and quarter"],
    },
    "Clipboard": {
        "color": "#f59e0b",
        "icon": "Clipboard",
        "desc": "Your clipboard is where text goes when you press Ctrl+C. These functions let the agent read and write to your clipboard automatically — great for copying results of operations, pasting data into forms, or keeping a history of everything you've recently copied.",
        "example": "Read what's on my clipboard and count the words",
        "bullets": ["Read whatever is currently on the clipboard", "Copy any text to the clipboard automatically", "Keep a history of recently copied items", "Monitor clipboard for changes", "Copy formatted code, file paths, and rich text"],
    },
    "Documents": {
        "color": "#ca8a04",
        "icon": "Documents",
        "desc": "Create, read, and edit document files. These tools can open Word documents, read PDFs, create spreadsheets, and work with plain text files — all without you having to open Microsoft Office or any other app. Great for automating reports and data extraction.",
        "example": "Read the text from my PDF report and summarize the key points",
        "bullets": ["Read text from PDF files", "Create and edit Word documents (.docx)", "Read and write Excel spreadsheets (.xlsx)", "Work with CSV files for tabular data", "Convert documents between different formats"],
    },
    "QR Code": {
        "color": "#0ea5e9",
        "icon": "QR Code",
        "desc": "QR codes are those square barcodes you see on menus and posters. These functions let you create QR codes for any text, URL, or data — and also read/decode QR codes from images. Useful for sharing links, making contact cards, or encoding information.",
        "example": "Create a QR code for my website URL",
        "bullets": ["Generate QR codes from any text or URL", "Customize QR code size and colors", "Decode QR codes from image files", "Create QR codes for WiFi, contacts, and more", "Save QR codes as PNG or SVG images"],
    },
    "UI": {
        "color": "#34d399",
        "icon": "UI",
        "desc": "These functions create small on-screen pop-up windows — like when you need to show a message, ask the user a question, or display a progress bar while something runs. Think of them as the tools for making little helper windows appear.",
        "example": "Show a notification saying the task is complete",
        "bullets": ["Show message boxes and alerts", "Create yes/no confirmation dialogs", "Display progress bars for long operations", "Show input dialogs to ask for text", "Create simple on-screen widgets"],
    },
    "Windows": {
        "color": "#0ea5e9",
        "icon": "Windows",
        "desc": "Control the windows and apps on your desktop. Move windows around, resize them, snap them side-by-side, bring a window to the front, minimize everything, and get info about what windows are currently open. Like a remote control for your desktop.",
        "example": "Arrange all my open windows side by side",
        "bullets": ["List all open windows and their positions", "Move and resize windows to exact coordinates", "Snap windows into split-screen layouts", "Minimize, maximize, and restore windows", "Bring a specific window to the foreground"],
    },
    "Scheduling": {
        "color": "#8b5cf6",
        "icon": "Scheduling",
        "desc": "Run things automatically at specific times. Set up a task to run every morning, once a week, or at a specific date. Like setting an alarm, but instead of waking you up, it runs an automation. Useful for daily backups, cleanup tasks, and reminders.",
        "example": "Schedule a system cleanup to run every Sunday at midnight",
        "bullets": ["Run tasks at a specific time or date", "Repeat tasks on a schedule (daily, weekly)", "Run a task after a delay", "List and cancel scheduled tasks", "Log what ran and when"],
    },
    "Input Control": {
        "color": "#f43f5e",
        "icon": "Input Control",
        "desc": "Simulate keyboard presses and mouse movements without touching the real keyboard or mouse. These functions let the agent type text, click buttons, move the cursor, scroll pages, and press keyboard shortcuts — essentially remote-controlling your computer's input devices.",
        "example": "Type my email address and press Tab to go to the next field",
        "bullets": ["Type text into any focused window", "Click, double-click, and right-click anywhere", "Press keyboard shortcuts like Ctrl+C or Alt+F4", "Scroll up, down, left, right on any page", "Move the mouse to specific coordinates"],
    },
    "Notifications": {
        "color": "#22c55e",
        "icon": "Notifications",
        "desc": "Send pop-up notifications to the Windows notification area (bottom right of your screen). These appear like the alerts you get from apps — a small popup with a title and message. Good for alerting you when a long-running task is done.",
        "example": "Send me a notification when the file download is complete",
        "bullets": ["Show Windows toast notifications", "Set notification title, message, and icon", "Schedule notifications for later", "Play sound with notifications", "Show notifications from background tasks"],
    },
    "Browser": {
        "color": "#60a5fa",
        "icon": "Browser",
        "desc": "Control your web browser — open URLs, click links, fill in forms, scroll pages, and read the content of web pages. The agent can browse the internet the same way you do, making it powerful for research, filling out forms, and web scraping.",
        "example": "Open Chrome, go to Wikipedia, and search for artificial intelligence",
        "bullets": ["Open URLs in Chrome, Firefox, or Edge", "Click links and buttons on web pages", "Fill in form fields automatically", "Scroll through and read page content", "Take screenshots of specific web pages"],
    },
    "Other": {
        "color": "#888888",
        "icon": "Other",
        "desc": "A collection of useful tools that don't fit neatly into one category. Includes utilities for compression (zip/unzip files), testing and validation, math calculations, random data generation, and other helpful miscellaneous functions.",
        "example": "Compress my project folder into a ZIP file",
        "bullets": ["Compress files into ZIP, TAR, and other archives", "Extract any archive format", "Generate random numbers and test data", "Run validation and integrity checks", "Math and utility helper functions"],
    },
}


# ── Persistence helpers ──────────────────────────────────────────────────────
def load_json(path, default=None):
    if default is None:
        default = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def add_history_entry(task, actions, model, status="completed"):
    history = load_json(HISTORY_FILE)
    history.insert(0, {
        "timestamp": datetime.now().isoformat(),
        "task": task,
        "model": model,
        "steps": len(actions),
        "actions": actions[:50],  # cap stored actions
        "status": status,
    })
    history = history[:200]  # keep last 200 runs
    save_json(HISTORY_FILE, history)


# ── Mascot ───────────────────────────────────────────────────────────────────
def create_mascot(size=64):
    s = size
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = s // 2
    ant_x, ant_top, ant_base = cx, int(s*0.05), int(s*0.22)
    d.line([(ant_x, ant_base), (ant_x, ant_top)], fill="#60a5fa", width=max(2, s//28))
    d.ellipse([ant_x-s//16, ant_top-s//16, ant_x+s//16, ant_top+s//16], fill="#34d399", outline="#22c55e", width=1)
    hl, hr, ht, hb = int(s*0.18), int(s*0.82), int(s*0.20), int(s*0.52)
    d.rounded_rectangle([hl, ht, hr, hb], radius=s//10, fill="#1e3a5f", outline="#60a5fa", width=max(2, s//28))
    ey, er = int(s*0.34), int(s*0.065)
    for ex in [int(s*0.34), int(s*0.66)]:
        gr = er + s//20
        d.ellipse([ex-gr, ey-gr, ex+gr, ey+gr], fill=(52,211,153,60))
        d.ellipse([ex-er, ey-er, ex+er, ey+er], fill="#34d399", outline="#86efac", width=1)
        pr = max(1, er//2)
        d.ellipse([ex-pr, ey-pr, ex+pr, ey+pr], fill="#0f172a")
    d.arc([int(s*0.35), int(s*0.42), int(s*0.65), int(s*0.48)], start=0, end=180, fill="#60a5fa", width=max(2, s//28))
    ew, eh, eey = int(s*0.06), int(s*0.12), int(s*0.32)
    d.rounded_rectangle([hl-ew-2, eey, hl-1, eey+eh], radius=2, fill="#60a5fa")
    d.rounded_rectangle([hr+1, eey, hr+ew+2, eey+eh], radius=2, fill="#60a5fa")
    bl, br, bt, bb = int(s*0.22), int(s*0.78), int(s*0.54), int(s*0.80)
    d.rounded_rectangle([bl, bt, br, bb], radius=s//12, fill="#1e3a5f", outline="#60a5fa", width=max(2, s//28))
    sl, sr_, st, sb = int(s*0.32), int(s*0.68), int(s*0.58), int(s*0.72)
    d.rounded_rectangle([sl, st, sr_, sb], radius=3, fill="#0f172a", outline="#34d399", width=1)
    for i in range(3):
        ly = st + 3 + i * int((sb-st-6)/3)
        d.line([(sl+4, ly), (sr_-4, ly)], fill=(52,211,153,120), width=1)
    aw = max(2, s//20)
    d.line([(bl-2, int(s*0.58)), (int(s*0.12), int(s*0.68))], fill="#60a5fa", width=aw)
    d.ellipse([int(s*0.08), int(s*0.66), int(s*0.16), int(s*0.74)], fill="#34d399")
    d.line([(br+2, int(s*0.58)), (int(s*0.88), int(s*0.68))], fill="#60a5fa", width=aw)
    d.ellipse([int(s*0.84), int(s*0.66), int(s*0.92), int(s*0.74)], fill="#34d399")
    lw = max(2, s//20)
    d.line([(int(s*0.38), bb), (int(s*0.34), int(s*0.90))], fill="#60a5fa", width=lw)
    d.line([(int(s*0.62), bb), (int(s*0.66), int(s*0.90))], fill="#60a5fa", width=lw)
    fr = max(2, s//16)
    d.ellipse([int(s*0.30), int(s*0.88), int(s*0.30)+fr*2, int(s*0.88)+fr*2], fill="#60a5fa")
    d.ellipse([int(s*0.62), int(s*0.88), int(s*0.62)+fr*2, int(s*0.88)+fr*2], fill="#60a5fa")
    return img


# ══════════════════════════════════════════════════════════════════════════════
# Infrastructure classes
# ══════════════════════════════════════════════════════════════════════════════

class SubprocessManager:
    """Tracks launched tool PIDs and terminates them on app exit."""

    def __init__(self):
        self._procs = {}
        import atexit
        atexit.register(self.cleanup_all)

    def launch(self, name, cmd, cwd):
        """Launch a tool. Returns (pid, msg) or (None, error_msg)."""
        if name in self._procs and self._procs[name].poll() is None:
            pid = self._procs[name].pid
            return pid, f"{name} is already running (PID {pid})"
        try:
            proc = subprocess.Popen(cmd, shell=True, cwd=cwd,
                                     creationflags=subprocess.CREATE_NEW_PROCESS_GROUP)
            self._procs[name] = proc
            return proc.pid, f"Launched {name} (PID {proc.pid})"
        except Exception as e:
            return None, f"Failed: {e}"

    def is_running(self, name):
        return name in self._procs and self._procs[name].poll() is None

    def cleanup_all(self):
        for name, proc in self._procs.items():
            if proc.poll() is None:
                try:
                    proc.terminate()
                except Exception:
                    pass


class SettingsManager:
    """Persists user preferences to ~/.screen_agent/settings.json."""

    _DEFAULTS = {
        "theme": "Dark",
        "model": "",
        "always_on_top": True,
        "confirm_actions": False,
        "verbose": True,
        "sound": False,
        "max_steps": "50",
        "delay": "1.0",
        "screenshot_quality": "1280px",
    }

    def __init__(self):
        self._path = os.path.join(os.path.expanduser("~"), ".screen_agent", "settings.json")
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        self._data = dict(self._DEFAULTS)
        self._load()

    def _load(self):
        try:
            if os.path.isfile(self._path):
                with open(self._path, "r") as f:
                    saved = json.load(f)
                self._data.update(saved)
        except (json.JSONDecodeError, OSError):
            pass

    def save(self):
        try:
            with open(self._path, "w") as f:
                json.dump(self._data, f, indent=2)
        except OSError:
            pass

    def get(self, key):
        return self._data.get(key, self._DEFAULTS.get(key))

    def update(self, key, value):
        self._data[key] = value
        self.save()


# Categories that require user confirmation before executing write operations
DANGEROUS_CATEGORIES = {"System", "Security", "Network", "Files", "Docker", "Windows"}
SAFE_PREFIXES = ("get_", "list_", "show_", "check_", "is_", "has_", "search_", "count_", "find_")


# ══════════════════════════════════════════════════════════════════════════════
class ScreenAgent:
    def __init__(self):
        self._proc_mgr = SubprocessManager()
        self._settings = SettingsManager()
        self.running = False
        self.paused = False
        self.thread = None
        self.action_history = []
        self.available_models = []
        self.selected_model = None
        self.model_loaded = False
        self.screen_width = pyautogui.size()[0]
        self.screen_height = pyautogui.size()[1]
        self.saved_tasks = load_json(SAVED_TASKS_FILE)

        ctk.set_appearance_mode(self._settings.get("theme").lower())
        self._build_gui()
        self._detect_models()

        # Restore saved model selection
        saved_model = self._settings.get("model")
        if saved_model and saved_model in self.available_models:
            self.model_var.set(saved_model)

    # ── clipboard helper ──
    def _copy_to_clipboard(self, text):
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self._set_status("Copied!", "#34d399")
        self.root.after(1500, lambda: self._set_status("Ready", "#888888"))

    def _change_theme(self, choice):
        ctk.set_appearance_mode(choice.lower())

    # ══════════════════════════════════════════════════════════════════════
    #  GUI
    # ══════════════════════════════════════════════════════════════════════
    def _build_gui(self):
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("Screen Agent")
        self.root.geometry("800x960")
        self.root.attributes("-topmost", True)
        self.root.minsize(620, 700)

        icon_img = create_mascot(64)
        icon_photo = ImageTk.PhotoImage(icon_img)
        self.root.iconphoto(False, icon_photo)
        self._icon_ref = icon_photo

        # ══ INPUT BAR AT TOP ══
        input_frame = ctk.CTkFrame(self.root, fg_color="#1e1e2e", corner_radius=10)
        input_frame.pack(fill="x", padx=10, pady=(8, 4))

        # Row 1: Input box with paste/copy
        input_top = ctk.CTkFrame(input_frame, fg_color="transparent")
        input_top.pack(fill="x", padx=8, pady=(8, 4))

        self.input_box = ctk.CTkTextbox(input_top, height=44, font=("Segoe UI", 13),
                                         corner_radius=8)
        self.input_box.pack(fill="x", side="left", expand=True, padx=(0, 5))
        self.input_box.bind("<Return>", self._on_enter)
        self.input_box.bind("<Shift-Return>", lambda e: None)
        self.input_box.bind("<Button-3>", self._show_input_context_menu)
        self.input_box.bind("<Control-a>", lambda e: (self.input_box.tag_add("sel", "1.0", "end"), "break")[1])

        # Clipboard buttons next to input
        clip_frame = ctk.CTkFrame(input_top, fg_color="transparent", width=50)
        clip_frame.pack(side="right")

        ctk.CTkButton(clip_frame, text="Paste", width=50, height=20,
                      font=("Segoe UI", 10), fg_color="#555555", hover_color="#666666",
                      command=self._paste_to_input).pack(pady=(0, 2))
        ctk.CTkButton(clip_frame, text="Copy", width=50, height=20,
                      font=("Segoe UI", 10), fg_color="#555555", hover_color="#666666",
                      command=self._copy_input).pack()

        # Row 2: Action buttons
        btn_frame = ctk.CTkFrame(input_frame, fg_color="transparent")
        btn_frame.pack(fill="x", padx=8, pady=(0, 8))

        self.run_btn = ctk.CTkButton(btn_frame, text="Run", width=80, height=32,
                                      font=("Segoe UI", 13, "bold"),
                                      fg_color="#2563eb", hover_color="#1d4ed8",
                                      command=self._start_agent)
        self.run_btn.pack(side="left")

        self.pause_btn = ctk.CTkButton(btn_frame, text="Pause", width=65, height=32,
                                        font=("Segoe UI", 12),
                                        fg_color="#ca8a04", hover_color="#a16207",
                                        command=self._toggle_pause, state="disabled")
        self.pause_btn.pack(side="left", padx=4)

        self.stop_btn = ctk.CTkButton(btn_frame, text="Stop", width=60, height=32,
                                       font=("Segoe UI", 12),
                                       fg_color="#dc2626", hover_color="#b91c1c",
                                       command=self._stop_agent, state="disabled")
        self.stop_btn.pack(side="left")

        ctk.CTkButton(btn_frame, text="Save Task", width=75, height=32,
                      font=("Segoe UI", 12), fg_color="#f59e0b", hover_color="#d97706",
                      text_color="#000000",
                      command=self._save_current_task).pack(side="left", padx=(8, 0))

        self.clear_btn = ctk.CTkButton(btn_frame, text="Clear", width=60, height=32,
                                        font=("Segoe UI", 12),
                                        fg_color="#555555", hover_color="#444444",
                                        command=self._clear_chat)
        self.clear_btn.pack(side="right")

        # Status indicator in button bar
        self.status_dot = ctk.CTkLabel(btn_frame, text="", width=10, height=10, fg_color="#555555", corner_radius=5)
        self.status_dot.pack(side="right", padx=(0, 4))
        self.status_label = ctk.CTkLabel(btn_frame, text="Ready", font=("Segoe UI", 11), text_color="#888888")
        self.status_label.pack(side="right", padx=(0, 4))

        # ── Tab view ──
        self.tabview = ctk.CTkTabview(self.root, fg_color="transparent",
                                       segmented_button_fg_color="#1e1e2e",
                                       segmented_button_selected_color="#2563eb")
        self.tabview.pack(fill="both", expand=True, padx=10, pady=(2, 8))

        self.tab_main = self.tabview.add("Agent")
        self.tab_tools = self.tabview.add("Tools")
        self.tab_coder = self.tabview.add("AI Coder")
        self.tab_clipboard = self.tabview.add("Clipboard")
        self.tab_history = self.tabview.add("History")
        self.tab_saved = self.tabview.add("Saved Tasks")
        self.tab_settings = self.tabview.add("Settings")

        self._build_main_tab()
        self._build_tools_tab()
        self._build_coder_tab()
        self._build_clipboard_tab()
        self._build_history_tab()
        self._build_saved_tab()
        self._build_settings_tab()

    # ── Main Agent Tab ──
    def _build_main_tab(self):
        scroll = ctk.CTkScrollableFrame(self.tab_main, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # Header
        header = ctk.CTkFrame(scroll, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(10, 5))

        mascot_pil = create_mascot(42)
        self._mascot_img = ctk.CTkImage(light_image=mascot_pil, dark_image=mascot_pil, size=(42, 42))
        ctk.CTkLabel(header, image=self._mascot_img, text="").pack(side="left", padx=(0, 8))
        ctk.CTkLabel(header, text="Screen Agent", font=("Segoe UI", 22, "bold")).pack(side="left")

        # ── Model Section ──
        model_sec = ctk.CTkFrame(scroll, fg_color="#1e1e2e", corner_radius=10)
        model_sec.pack(fill="x", padx=10, pady=4)

        mh = ctk.CTkFrame(model_sec, fg_color="transparent")
        mh.pack(fill="x", padx=10, pady=(8, 4))
        ctk.CTkLabel(mh, text="Model", font=("Segoe UI", 14, "bold")).pack(side="left")
        self.model_status_label = ctk.CTkLabel(mh, text="No model loaded", font=("Segoe UI", 11), text_color="#888888")
        self.model_status_label.pack(side="right")

        mr = ctk.CTkFrame(model_sec, fg_color="transparent")
        mr.pack(fill="x", padx=10, pady=4)
        self.model_var = ctk.StringVar(value="Detecting...")
        self.model_dropdown = ctk.CTkOptionMenu(mr, variable=self.model_var, values=["Detecting..."], width=200, font=("Segoe UI", 12))
        self.model_dropdown.pack(side="left")
        self.activate_btn = ctk.CTkButton(mr, text="Activate", width=80, font=("Segoe UI", 12, "bold"),
                                           fg_color="#22c55e", hover_color="#16a34a", command=self._activate_model, state="disabled")
        self.activate_btn.pack(side="left", padx=(6, 0))

        gr = ctk.CTkFrame(model_sec, fg_color="transparent")
        gr.pack(fill="x", padx=10, pady=(4, 8))
        self.grab_var = ctk.StringVar(value="llava-cracked")
        self.grab_dropdown = ctk.CTkOptionMenu(gr, variable=self.grab_var,
                          values=["llava-cracked", "bakllava-cracked", "llama3.2-vision-cracked",
                                  "minicpm-v-cracked"],
                          width=200, font=("Segoe UI", 12))
        self.grab_dropdown.pack(side="left")
        self.pull_btn = ctk.CTkButton(gr, text="Grab Model", width=90, font=("Segoe UI", 12),
                                       fg_color="#7c3aed", hover_color="#6d28d9", command=self._pull_model)
        self.pull_btn.pack(side="left", padx=(6, 0))
        ctk.CTkButton(gr, text="Refresh", width=65, font=("Segoe UI", 11),
                      fg_color="#555555", hover_color="#444444", command=self._detect_models).pack(side="right")

        # ── Options Section ──
        opt_sec = ctk.CTkFrame(scroll, fg_color="#1e1e2e", corner_radius=10)
        opt_sec.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(opt_sec, text="Options", font=("Segoe UI", 14, "bold")).pack(anchor="w", padx=10, pady=(8, 4))

        r1 = ctk.CTkFrame(opt_sec, fg_color="transparent")
        r1.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(r1, text="Max Steps:", font=("Segoe UI", 12)).pack(side="left")
        self.steps_var = ctk.StringVar(value=self._settings.get("max_steps"))
        self.steps_var.trace_add("write", lambda *_: self._settings.update("max_steps", self.steps_var.get()))
        ctk.CTkEntry(r1, textvariable=self.steps_var, width=50, font=("Segoe UI", 12)).pack(side="left", padx=(4, 0))
        ctk.CTkLabel(r1, text="Actions before auto-stop", font=("Segoe UI", 10), text_color="#777").pack(side="left", padx=(6, 0))

        r2 = ctk.CTkFrame(opt_sec, fg_color="transparent")
        r2.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(r2, text="Delay (s):", font=("Segoe UI", 12)).pack(side="left")
        self.delay_var = ctk.StringVar(value=self._settings.get("delay"))
        self.delay_var.trace_add("write", lambda *_: self._settings.update("delay", self.delay_var.get()))
        ctk.CTkEntry(r2, textvariable=self.delay_var, width=50, font=("Segoe UI", 12)).pack(side="left", padx=(4, 0))
        ctk.CTkLabel(r2, text="Pause between actions", font=("Segoe UI", 10), text_color="#777").pack(side="left", padx=(6, 0))

        r3 = ctk.CTkFrame(opt_sec, fg_color="transparent")
        r3.pack(fill="x", padx=10, pady=2)
        self.topmost_var = ctk.BooleanVar(value=self._settings.get("always_on_top"))
        ctk.CTkCheckBox(r3, text="Always on top", variable=self.topmost_var, font=("Segoe UI", 12),
                        command=lambda: (self.root.attributes("-topmost", self.topmost_var.get()),
                                         self._settings.update("always_on_top", self.topmost_var.get()))).pack(side="left")
        self.confirm_var = ctk.BooleanVar(value=self._settings.get("confirm_actions"))
        ctk.CTkCheckBox(r3, text="Confirm actions", variable=self.confirm_var, font=("Segoe UI", 12),
                        command=lambda: self._settings.update("confirm_actions", self.confirm_var.get())).pack(side="left", padx=(12, 0))

        r4 = ctk.CTkFrame(opt_sec, fg_color="transparent")
        r4.pack(fill="x", padx=10, pady=2)
        self.verbose_var = ctk.BooleanVar(value=self._settings.get("verbose"))
        ctk.CTkCheckBox(r4, text="Verbose log", variable=self.verbose_var, font=("Segoe UI", 12),
                        command=lambda: self._settings.update("verbose", self.verbose_var.get())).pack(side="left")
        self.sound_var = ctk.BooleanVar(value=self._settings.get("sound"))
        ctk.CTkCheckBox(r4, text="Sound on done", variable=self.sound_var, font=("Segoe UI", 12),
                        command=lambda: self._settings.update("sound", self.sound_var.get())).pack(side="left", padx=(12, 0))

        r5 = ctk.CTkFrame(opt_sec, fg_color="transparent")
        r5.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(r5, text="Screenshot:", font=("Segoe UI", 12)).pack(side="left")
        self.quality_var = ctk.StringVar(value=self._settings.get("screenshot_quality"))
        self.quality_var.trace_add("write", lambda *_: self._settings.update("screenshot_quality", self.quality_var.get()))
        ctk.CTkOptionMenu(r5, variable=self.quality_var,
                          values=["640px (fast)", "1280px (balanced)", "1920px (full)", "Original"],
                          width=160, font=("Segoe UI", 11)).pack(side="left", padx=(6, 0))

        r6 = ctk.CTkFrame(opt_sec, fg_color="transparent")
        r6.pack(fill="x", padx=10, pady=(2, 8))
        ctk.CTkLabel(r6, text="Theme:", font=("Segoe UI", 12)).pack(side="left")
        self.theme_var = ctk.StringVar(value=self._settings.get("theme"))
        self.theme_var.trace_add("write", lambda *_: self._settings.update("theme", self.theme_var.get()))
        ctk.CTkOptionMenu(r6, variable=self.theme_var,
                          values=["Dark", "Light", "System"],
                          width=100, font=("Segoe UI", 11),
                          command=self._change_theme).pack(side="left", padx=(6, 0))
        ctk.CTkLabel(r6, text="Switch between dark and light appearance",
                     font=("Segoe UI", 10), text_color="#777").pack(side="left", padx=(6, 0))

        # ── Automations ──
        ctk.CTkLabel(scroll, text="Automations", font=("Segoe UI", 16, "bold")).pack(
            anchor="w", padx=10, pady=(8, 2))
        ctk.CTkLabel(scroll, text="Click any card to load it. Tasks marked with '...' need you to fill in details.",
                     font=("Segoe UI", 11), text_color="#777").pack(anchor="w", padx=10, pady=(0, 6))

        # Group automations by category
        auto_cats = {}
        for name, desc, cat, steps, prompt, needs_input in AUTOMATIONS:
            auto_cats.setdefault(cat, []).append((name, desc, steps, prompt, needs_input))

        # Render Long Automations first, then the rest
        cat_order = ["Long Automation"] + [c for c in auto_cats if c != "Long Automation"]

        for cat in cat_order:
            tasks = auto_cats.get(cat, [])
            if not tasks:
                continue

            color = CAT_COLORS.get(cat, "#888")
            cat_desc = CAT_ICONS.get(cat, "")

            cat_sec = ctk.CTkFrame(scroll, fg_color="#1e1e2e", corner_radius=10)
            cat_sec.pack(fill="x", padx=10, pady=4)

            # Category header with description
            ch = ctk.CTkFrame(cat_sec, fg_color="transparent")
            ch.pack(fill="x", padx=10, pady=(8, 2))
            ctk.CTkLabel(ch, text=cat, font=("Segoe UI", 14, "bold"), text_color=color).pack(side="left")
            ctk.CTkLabel(ch, text=f"{len(tasks)} tasks", font=("Segoe UI", 11),
                         text_color="#666").pack(side="right")

            if cat_desc:
                ctk.CTkLabel(cat_sec, text=cat_desc, font=("Segoe UI", 11),
                             text_color="#888").pack(anchor="w", padx=10, pady=(0, 6))

            # Task cards
            for name, desc, steps, prompt, needs_input in tasks:
                card = ctk.CTkFrame(cat_sec, fg_color="#0f0f1a", corner_radius=8)
                card.pack(fill="x", padx=10, pady=3)

                # Top row: name + steps badge + run button
                top = ctk.CTkFrame(card, fg_color="transparent")
                top.pack(fill="x", padx=10, pady=(8, 2))

                title_text = f"{name} ..." if needs_input else name
                ctk.CTkLabel(top, text=title_text, font=("Segoe UI", 13, "bold"),
                             text_color="#e0e0e0").pack(side="left")

                # Run button
                ctk.CTkButton(top, text="Run", width=50, height=24,
                              font=("Segoe UI", 11, "bold"),
                              fg_color=color, hover_color="#444",
                              command=lambda n=name, d=desc, p=prompt, ni=needs_input:
                                  self._load_automation(n, d, p, ni)).pack(side="right")

                # Steps badge
                ctk.CTkLabel(top, text=steps, font=("Segoe UI", 10),
                             text_color="#666", fg_color="#1a1a2e",
                             corner_radius=4, width=60).pack(side="right", padx=(0, 6))

                # Description
                ctk.CTkLabel(card, text=desc, font=("Segoe UI", 11),
                             text_color="#999", anchor="w", justify="left",
                             wraplength=620).pack(fill="x", padx=10, pady=(0, 8))

            ctk.CTkLabel(cat_sec, text="", height=2).pack()

        # ── Chat Log ──
        chat_header = ctk.CTkFrame(scroll, fg_color="transparent")
        chat_header.pack(fill="x", padx=10, pady=(8, 2))
        ctk.CTkLabel(chat_header, text="Chat Log", font=("Segoe UI", 14, "bold")).pack(side="left")
        ctk.CTkButton(chat_header, text="Copy All", width=70, height=26, font=("Segoe UI", 11),
                      fg_color="#555555", hover_color="#666666",
                      command=self._copy_chat_log).pack(side="right")

        self.chat_frame = ctk.CTkScrollableFrame(scroll, fg_color="#1a1a1a", corner_radius=10, height=220)
        self.chat_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        self._add_system_msg("Screen Agent ready. Pick an automation above or type your own command.")
        self._add_system_msg(f"Screen: {self.screen_width}x{self.screen_height} | Emergency stop: move mouse to top-left corner.")
        if TOOLKIT_AVAILABLE:
            stats = get_registry().get_stats()
            self._add_system_msg(f"Toolkit loaded: {stats['total_tools']} functions across {stats['total_modules']} modules. Check the Tools tab to browse everything available.")

    # ── Tools Tab ── (COMPLETE REWRITE: dynamic function browser)

    # ── History Tab ──
    def _build_history_tab(self):
        toolbar = ctk.CTkFrame(self.tab_history, fg_color="transparent")
        toolbar.pack(fill="x", padx=10, pady=(10, 5))
        ctk.CTkLabel(toolbar, text="Run History", font=("Segoe UI", 16, "bold")).pack(side="left")
        ctk.CTkButton(toolbar, text="Refresh", width=70, height=28, font=("Segoe UI", 12),
                      fg_color="#555555", hover_color="#444444",
                      command=self._refresh_history).pack(side="right")
        ctk.CTkButton(toolbar, text="Clear History", width=90, height=28, font=("Segoe UI", 12),
                      fg_color="#dc2626", hover_color="#b91c1c",
                      command=self._clear_history).pack(side="right", padx=(0, 6))

        self.history_scroll = ctk.CTkScrollableFrame(self.tab_history, fg_color="#1a1a1a", corner_radius=10)
        self.history_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._refresh_history()

    def _refresh_history(self):
        for w in self.history_scroll.winfo_children():
            w.destroy()

        history = load_json(HISTORY_FILE)
        if not history:
            ctk.CTkLabel(self.history_scroll, text="No history yet. Run a task to see it here.",
                         font=("Segoe UI", 13), text_color="#666").pack(pady=20)
            return

        for i, entry in enumerate(history[:50]):
            ts = entry.get("timestamp", "")
            try:
                dt = datetime.fromisoformat(ts)
                time_str = dt.strftime("%b %d, %H:%M")
            except Exception:
                time_str = ts[:16]

            task = entry.get("task", "Unknown")
            model = entry.get("model", "?")
            steps = entry.get("steps", 0)
            status = entry.get("status", "?")

            row = ctk.CTkFrame(self.history_scroll, fg_color="#1e1e2e", corner_radius=8)
            row.pack(fill="x", padx=5, pady=3)

            # Top row: time + status
            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=8, pady=(6, 2))

            status_color = "#22c55e" if status == "completed" else "#f87171"
            ctk.CTkLabel(top, text=time_str, font=("Segoe UI", 11), text_color="#888").pack(side="left")
            ctk.CTkLabel(top, text=f"{status}  |  {steps} steps  |  {model}",
                         font=("Segoe UI", 11), text_color=status_color).pack(side="left", padx=(8, 0))

            # Copy & Reuse buttons
            ctk.CTkButton(top, text="Reuse", width=50, height=22, font=("Segoe UI", 10),
                          fg_color="#2563eb", hover_color="#1d4ed8",
                          command=lambda t=task: self._reuse_history_task(t)).pack(side="right", padx=(4, 0))
            ctk.CTkButton(top, text="Copy", width=45, height=22, font=("Segoe UI", 10),
                          fg_color="#555555", hover_color="#666666",
                          command=lambda t=task: self._copy_to_clipboard(t)).pack(side="right")

            # Task text (truncated)
            display = task[:120] + "..." if len(task) > 120 else task
            ctk.CTkLabel(row, text=display, font=("Segoe UI", 12), text_color="#ccc",
                         anchor="w", justify="left", wraplength=650).pack(fill="x", padx=8, pady=(0, 2))

            # Expandable actions
            actions = entry.get("actions", [])
            if actions:
                def make_toggle(parent, acts):
                    expanded = [False]
                    act_frame = ctk.CTkFrame(parent, fg_color="#0f0f1a", corner_radius=5)

                    def toggle():
                        if expanded[0]:
                            act_frame.pack_forget()
                            expanded[0] = False
                        else:
                            act_frame.pack(fill="x", padx=8, pady=(0, 6))
                            for a in acts[:20]:
                                af = ctk.CTkFrame(act_frame, fg_color="transparent")
                                af.pack(fill="x", padx=6, pady=1)
                                ctk.CTkLabel(af, text=a, font=("Segoe UI", 10), text_color="#999",
                                             anchor="w", wraplength=600).pack(side="left", fill="x", expand=True)
                                ctk.CTkButton(af, text="cp", width=28, height=18, font=("Segoe UI", 9),
                                              fg_color="#333", hover_color="#444",
                                              command=lambda txt=a: self._copy_to_clipboard(txt)).pack(side="right")
                            expanded[0] = True

                    ctk.CTkButton(parent, text=f"Show {len(acts)} actions", width=120, height=22,
                                  font=("Segoe UI", 10), fg_color="#333", hover_color="#444",
                                  command=toggle).pack(anchor="w", padx=8, pady=(0, 6))

                make_toggle(row, actions)

    def _reuse_history_task(self, task):
        self.tabview.set("Agent")
        self.input_box.delete("1.0", "end")
        self.input_box.insert("1.0", task)

    def _clear_history(self):
        save_json(HISTORY_FILE, [])
        self._refresh_history()

    # ── Saved Tasks Tab ──
    def _build_saved_tab(self):
        toolbar = ctk.CTkFrame(self.tab_saved, fg_color="transparent")
        toolbar.pack(fill="x", padx=10, pady=(10, 5))
        ctk.CTkLabel(toolbar, text="Saved Tasks", font=("Segoe UI", 16, "bold")).pack(side="left")
        ctk.CTkButton(toolbar, text="Refresh", width=70, height=28, font=("Segoe UI", 12),
                      fg_color="#555555", hover_color="#444444",
                      command=self._refresh_saved).pack(side="right")

        self.saved_scroll = ctk.CTkScrollableFrame(self.tab_saved, fg_color="#1a1a1a", corner_radius=10)
        self.saved_scroll.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        self._refresh_saved()

    def _refresh_saved(self):
        for w in self.saved_scroll.winfo_children():
            w.destroy()

        self.saved_tasks = load_json(SAVED_TASKS_FILE)
        if not self.saved_tasks:
            ctk.CTkLabel(self.saved_scroll, text="No saved tasks yet. Type a command and click 'Save Task'.",
                         font=("Segoe UI", 13), text_color="#666").pack(pady=20)
            return

        for i, task in enumerate(self.saved_tasks):
            name = task.get("name", f"Task {i+1}")
            prompt = task.get("prompt", "")
            created = task.get("created", "")

            row = ctk.CTkFrame(self.saved_scroll, fg_color="#1e1e2e", corner_radius=8)
            row.pack(fill="x", padx=5, pady=3)

            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=8, pady=(6, 2))

            ctk.CTkLabel(top, text=name, font=("Segoe UI", 13, "bold"), text_color="#f59e0b").pack(side="left")
            if created:
                ctk.CTkLabel(top, text=created[:10], font=("Segoe UI", 10), text_color="#666").pack(side="left", padx=(8, 0))

            # Buttons
            ctk.CTkButton(top, text="Delete", width=50, height=22, font=("Segoe UI", 10),
                          fg_color="#dc2626", hover_color="#b91c1c",
                          command=lambda idx=i: self._delete_saved_task(idx)).pack(side="right", padx=(4, 0))
            ctk.CTkButton(top, text="Copy", width=45, height=22, font=("Segoe UI", 10),
                          fg_color="#555555", hover_color="#666666",
                          command=lambda p=prompt: self._copy_to_clipboard(p)).pack(side="right", padx=(4, 0))
            ctk.CTkButton(top, text="Load", width=45, height=22, font=("Segoe UI", 10),
                          fg_color="#2563eb", hover_color="#1d4ed8",
                          command=lambda p=prompt: self._load_saved_task(p)).pack(side="right")

            display = prompt[:150] + "..." if len(prompt) > 150 else prompt
            ctk.CTkLabel(row, text=display, font=("Segoe UI", 12), text_color="#ccc",
                         anchor="w", justify="left", wraplength=650).pack(fill="x", padx=8, pady=(0, 6))

    # ── Tools Tab ── (dynamic function browser)
    def _build_tools_tab(self):
        # ── Header ──
        hdr_frame = ctk.CTkFrame(self.tab_tools, fg_color="#1e1e2e", corner_radius=0)
        hdr_frame.pack(fill="x", padx=0, pady=0)

        hdr_inner = ctk.CTkFrame(hdr_frame, fg_color="transparent")
        hdr_inner.pack(fill="x", padx=14, pady=(10, 8))

        ctk.CTkLabel(hdr_inner, text="Tools Browser", font=("Segoe UI", 18, "bold")).pack(side="left")

        if TOOLKIT_AVAILABLE:
            stats = get_registry().get_stats()
            stats_text = f"{stats['total_tools']:,} tools  |  {stats['total_modules']} modules  |  {stats.get('total_categories', 22)} categories"
        else:
            stats_text = "Toolkit not loaded"
        ctk.CTkLabel(hdr_inner, text=stats_text, font=("Segoe UI", 11), text_color="#34d399").pack(side="right")

        # ── Search bar ──
        search_frame = ctk.CTkFrame(self.tab_tools, fg_color="#161622", corner_radius=0)
        search_frame.pack(fill="x", padx=0, pady=0)

        search_inner = ctk.CTkFrame(search_frame, fg_color="transparent")
        search_inner.pack(fill="x", padx=14, pady=8)

        self.tools_search_var = ctk.StringVar()
        self._tools_search_entry = ctk.CTkEntry(
            search_inner,
            textvariable=self.tools_search_var,
            placeholder_text="Search all tools... (e.g. 'password', 'cpu', 'image', 'rename')",
            font=("Segoe UI", 13),
            height=36,
            corner_radius=8,
        )
        self._tools_search_entry.pack(side="left", fill="x", expand=True)
        self._tools_search_entry.bind("<Return>", lambda e: self._search_tools_live())
        self.tools_search_var.trace_add("write", lambda *_: self._search_tools_live())

        ctk.CTkButton(
            search_inner, text="Clear", width=60, height=36,
            font=("Segoe UI", 12), fg_color="#444", hover_color="#555",
            command=self._clear_tools_search
        ).pack(side="right", padx=(6, 0))

        # ── Search results panel (hidden until search) ──
        self._tools_search_panel = ctk.CTkScrollableFrame(
            self.tab_tools, fg_color="#0f0f1a", corner_radius=8, height=300
        )
        # Not packed initially — appears when user types

        # ── Category scroll area ──
        self._tools_cat_scroll = ctk.CTkScrollableFrame(self.tab_tools, fg_color="transparent")
        self._tools_cat_scroll.pack(fill="both", expand=True, padx=10, pady=(4, 8))

        # Track which categories are expanded
        self._cat_expanded = {}
        self._cat_func_frames = {}

        self._build_category_cards()

    def _build_category_cards(self):
        """Build collapsible category cards for all 22 categories."""
        for w in self._tools_cat_scroll.winfo_children():
            w.destroy()

        if not TOOLKIT_AVAILABLE:
            ctk.CTkLabel(
                self._tools_cat_scroll,
                text="Toolkit not loaded. Make sure the toolkit folder is present.",
                font=("Segoe UI", 13), text_color="#888"
            ).pack(pady=40)
            return

        reg = get_registry()
        cat_counts = reg.list_categories()  # Dict[str, int]

        # Use CATEGORY_INFO order, then append any extra registry categories not in it
        ordered_cats = list(CATEGORY_INFO.keys())
        for c in cat_counts:
            if c not in ordered_cats:
                ordered_cats.append(c)

        for cat_name in ordered_cats:
            count = cat_counts.get(cat_name, 0)
            info = CATEGORY_INFO.get(cat_name, {
                "color": "#888888", "icon": cat_name,
                "desc": f"Functions in the {cat_name} category.",
                "example": f"Use {cat_name} tools",
                "bullets": [],
            })
            color = info["color"]

            # Outer card
            card = ctk.CTkFrame(self._tools_cat_scroll, fg_color="#1e1e2e", corner_radius=10)
            card.pack(fill="x", padx=2, pady=4)

            # ── Category header row ──
            hdr = ctk.CTkFrame(card, fg_color="transparent")
            hdr.pack(fill="x", padx=10, pady=(8, 4))

            # Color accent bar
            ctk.CTkLabel(hdr, text="", width=5, height=24, fg_color=color,
                         corner_radius=3).pack(side="left", padx=(0, 8))

            # Category name
            ctk.CTkLabel(hdr, text=cat_name, font=("Segoe UI", 14, "bold"),
                         text_color="#e8e8e8").pack(side="left")

            # Tool count badge
            ctk.CTkLabel(hdr, text=f"{count} tools", font=("Segoe UI", 11),
                         text_color="#888", fg_color="#0f0f1a",
                         corner_radius=5, width=60).pack(side="left", padx=(8, 0))

            # Right-side buttons
            btn_frame = ctk.CTkFrame(hdr, fg_color="transparent")
            btn_frame.pack(side="right")

            ctk.CTkButton(
                btn_frame, text="Try Example", width=90, height=26,
                font=("Segoe UI", 10, "bold"),
                fg_color=color, hover_color="#444",
                command=lambda ex=info["example"]: self._try_capability(ex)
            ).pack(side="right", padx=(4, 0))

            expand_btn = ctk.CTkButton(
                btn_frame, text="Show Functions", width=110, height=26,
                font=("Segoe UI", 10),
                fg_color="#2a2a3a", hover_color="#3a3a4a",
                command=lambda c=cat_name, card=card: self._toggle_category(c, card)
            )
            expand_btn.pack(side="right", padx=(4, 0))
            self._cat_expanded[cat_name] = {"btn": expand_btn, "expanded": False}

            # Description
            ctk.CTkLabel(card, text=info["desc"], font=("Segoe UI", 11),
                         text_color="#999", anchor="w", justify="left",
                         wraplength=680).pack(fill="x", padx=16, pady=(0, 4))

            # Bullet points (compact, 2-column feel)
            if info.get("bullets"):
                bullets_frame = ctk.CTkFrame(card, fg_color="transparent")
                bullets_frame.pack(fill="x", padx=16, pady=(0, 6))
                for bullet in info["bullets"]:
                    bf = ctk.CTkFrame(bullets_frame, fg_color="transparent")
                    bf.pack(fill="x", pady=1)
                    ctk.CTkLabel(bf, text=">", font=("Segoe UI", 10, "bold"),
                                 text_color=color, width=14).pack(side="left")
                    ctk.CTkLabel(bf, text=bullet, font=("Segoe UI", 10),
                                 text_color="#777", anchor="w").pack(side="left", padx=(4, 0))

            # Function list container (starts hidden)
            func_container = ctk.CTkFrame(card, fg_color="#0a0a14", corner_radius=8)
            self._cat_func_frames[cat_name] = func_container
            # Not packed yet — shows on expand

    def _toggle_category(self, cat_name, card):
        """Expand or collapse a category's function list."""
        state = self._cat_expanded.get(cat_name, {})
        btn = state.get("btn")
        is_expanded = state.get("expanded", False)
        func_container = self._cat_func_frames.get(cat_name)

        if is_expanded:
            # Collapse
            if func_container:
                func_container.pack_forget()
            if btn:
                btn.configure(text="Show Functions")
            state["expanded"] = False
        else:
            # Expand - load functions if not yet loaded
            if func_container:
                already_loaded = len(func_container.winfo_children()) > 0
                if not already_loaded:
                    self._load_category_functions(cat_name, func_container)
                func_container.pack(fill="x", padx=10, pady=(0, 10))
            if btn:
                btn.configure(text="Hide Functions")
            state["expanded"] = True

    def _load_category_functions(self, cat_name, container):
        """Load the function rows into a category container."""
        if not TOOLKIT_AVAILABLE:
            return

        reg = get_registry()
        tools = reg.list_tools(category=cat_name)
        total = len(tools)

        if not tools:
            ctk.CTkLabel(container, text="No functions found in this category.",
                         font=("Segoe UI", 11), text_color="#666").pack(pady=8)
            return

        # Count label
        ctk.CTkLabel(
            container,
            text=f"  {total} functions in {cat_name}  —  Click a name for details  |  [Run] loads into Agent tab  |  [Copy] copies function name",
            font=("Segoe UI", 10), text_color="#555"
        ).pack(anchor="w", padx=10, pady=(6, 2))

        # Separator
        ctk.CTkFrame(container, height=1, fg_color="#222233").pack(fill="x", padx=10, pady=2)

        initial_limit = 20
        display_tools = tools[:initial_limit]

        rows_frame = ctk.CTkFrame(container, fg_color="transparent")
        rows_frame.pack(fill="x", padx=6, pady=2)

        def render_tool_rows(tool_list, parent_frame, alt_start=0):
            for idx, t in enumerate(tool_list):
                bg = "#0f0f1a" if (alt_start + idx) % 2 == 0 else "#12121f"
                row = ctk.CTkFrame(parent_frame, fg_color=bg, corner_radius=4)
                row.pack(fill="x", padx=2, pady=1)

                left = ctk.CTkFrame(row, fg_color="transparent")
                left.pack(side="left", fill="x", expand=True, padx=6, pady=4)

                name_lbl = ctk.CTkLabel(
                    left, text=t["name"], font=("Segoe UI", 11, "bold"),
                    text_color="#c0c0e0", anchor="w", cursor="hand2"
                )
                name_lbl.pack(anchor="w")
                name_lbl.bind("<Button-1>", lambda e, tool=t: self._show_tool_detail(tool))

                doc_short = (t.get("doc") or "No description available.")[:90]
                ctk.CTkLabel(
                    left, text=doc_short, font=("Segoe UI", 10),
                    text_color="#666", anchor="w"
                ).pack(anchor="w")

                right = ctk.CTkFrame(row, fg_color="transparent")
                right.pack(side="right", padx=6, pady=4)

                ctk.CTkButton(
                    right, text="Copy", width=50, height=22,
                    font=("Segoe UI", 10), fg_color="#2a2a3a", hover_color="#3a3a4a",
                    command=lambda tn=t["name"]: self._copy_to_clipboard(tn)
                ).pack(side="right", padx=(4, 0))

                ctk.CTkButton(
                    right, text="Run", width=44, height=22,
                    font=("Segoe UI", 10, "bold"), fg_color="#2563eb", hover_color="#1d4ed8",
                    command=lambda tn=t["name"], td=t.get("doc", ""): self._run_tool_prompt(tn, td)
                ).pack(side="right")

        render_tool_rows(display_tools, rows_frame, alt_start=0)

        # "Show all" button if more tools exist
        if total > initial_limit:
            more_frame = ctk.CTkFrame(container, fg_color="transparent")
            more_frame.pack(fill="x", padx=10, pady=(2, 6))

            remaining = total - initial_limit
            show_all_btn = [None]

            def load_all(tools=tools, parent=rows_frame, btn_holder=show_all_btn,
                         btn_frame=more_frame, loaded_so_far=initial_limit):
                render_tool_rows(tools[loaded_so_far:], parent, alt_start=loaded_so_far)
                if btn_holder[0]:
                    btn_holder[0].destroy()

            b = ctk.CTkButton(
                more_frame,
                text=f"Show all {total} functions ({remaining} more)...",
                width=260, height=26,
                font=("Segoe UI", 10), fg_color="#1a1a2e", hover_color="#2a2a3e",
                text_color="#888",
                command=load_all
            )
            b.pack(anchor="w")
            show_all_btn[0] = b

    def _run_tool_prompt(self, tool_name, doc=""):
        """Load a natural-language prompt for a tool into the Agent tab input."""
        short_doc = (doc or "").split("\n")[0][:80]
        prompt = f"Use the {tool_name} function. {short_doc}"
        self.tabview.set("Agent")
        self.input_box.delete("1.0", "end")
        self.input_box.insert("1.0", prompt)
        self._add_system_msg(f"Loaded tool prompt: {tool_name}\nHit Run to execute it.")

    def _show_tool_detail(self, tool):
        """Show a popup with full details about a function."""
        name = tool.get("name", "")
        doc = tool.get("doc") or "No description available."
        category = tool.get("category", "")

        popup = ctk.CTkToplevel(self.root)
        popup.title(f"Function: {name}")
        popup.geometry("560x420")
        popup.attributes("-topmost", True)
        popup.grab_set()

        scroll = ctk.CTkScrollableFrame(popup, fg_color="#0f0f1a")
        scroll.pack(fill="both", expand=True, padx=0, pady=0)

        # Header
        info = CATEGORY_INFO.get(category, {})
        color = info.get("color", "#888")

        hdr = ctk.CTkFrame(scroll, fg_color="#1e1e2e", corner_radius=8)
        hdr.pack(fill="x", padx=10, pady=(10, 4))

        ctk.CTkLabel(hdr, text="", width=5, height=20, fg_color=color,
                     corner_radius=3).pack(side="left", padx=(8, 6), pady=8)
        ctk.CTkLabel(hdr, text=name, font=("Segoe UI", 14, "bold"),
                     text_color="#e0e0e0").pack(side="left", pady=8)
        ctk.CTkLabel(hdr, text=category, font=("Segoe UI", 10),
                     text_color=color, fg_color="#0f0f1a",
                     corner_radius=4, width=80).pack(side="right", padx=8)

        # Description
        desc_frame = ctk.CTkFrame(scroll, fg_color="#1a1a2e", corner_radius=8)
        desc_frame.pack(fill="x", padx=10, pady=4)
        ctk.CTkLabel(desc_frame, text="Description", font=("Segoe UI", 11, "bold"),
                     text_color="#888").pack(anchor="w", padx=10, pady=(8, 2))
        ctk.CTkLabel(desc_frame, text=doc, font=("Segoe UI", 12),
                     text_color="#ccc", anchor="w", justify="left",
                     wraplength=500).pack(fill="x", padx=10, pady=(0, 10))

        # Parameters (if available)
        if TOOLKIT_AVAILABLE:
            reg = get_registry()
            info_full = reg.get_tool_info(name)
            if info_full and info_full.get("params"):
                p_frame = ctk.CTkFrame(scroll, fg_color="#1a1a2e", corner_radius=8)
                p_frame.pack(fill="x", padx=10, pady=4)
                ctk.CTkLabel(p_frame, text="Parameters", font=("Segoe UI", 11, "bold"),
                             text_color="#888").pack(anchor="w", padx=10, pady=(8, 4))

                for pname, pinfo in info_full["params"].items():
                    pr = ctk.CTkFrame(p_frame, fg_color="transparent")
                    pr.pack(fill="x", padx=10, pady=1)
                    req = " (required)" if pinfo.get("required") else f" = {pinfo.get('default', 'optional')}"
                    ptype = pinfo.get("type", "any")
                    label = f"{pname}: {ptype}{req}"
                    ctk.CTkLabel(pr, text=label, font=("Segoe UI", 10),
                                 text_color="#aaa", anchor="w").pack(side="left")

                ctk.CTkLabel(p_frame, text="", height=4).pack()

        # Buttons row
        btn_row = ctk.CTkFrame(scroll, fg_color="transparent")
        btn_row.pack(fill="x", padx=10, pady=(4, 10))

        ctk.CTkButton(
            btn_row, text="Copy Function Name", width=150, height=30,
            font=("Segoe UI", 11), fg_color="#2a2a3a", hover_color="#3a3a4a",
            command=lambda: self._copy_to_clipboard(name)
        ).pack(side="left")

        ctk.CTkButton(
            btn_row, text="Copy JSON Template", width=150, height=30,
            font=("Segoe UI", 11), fg_color="#2a2a3a", hover_color="#3a3a4a",
            command=lambda: self._copy_tool_json(name)
        ).pack(side="left", padx=(6, 0))

        ctk.CTkButton(
            btn_row, text="Load in Agent Tab", width=140, height=30,
            font=("Segoe UI", 11, "bold"), fg_color="#2563eb", hover_color="#1d4ed8",
            command=lambda: (self._run_tool_prompt(name, doc), popup.destroy())
        ).pack(side="right")

        ctk.CTkButton(
            btn_row, text="Close", width=70, height=30,
            font=("Segoe UI", 11), fg_color="#555", hover_color="#666",
            command=popup.destroy
        ).pack(side="right", padx=(0, 6))

    def _search_tools_live(self):
        """Live search — shows/hides the search results panel."""
        query = self.tools_search_var.get().strip()

        if not query:
            self._tools_search_panel.pack_forget()
            if not self._tools_cat_scroll.winfo_ismapped():
                self._tools_cat_scroll.pack(fill="both", expand=True, padx=10, pady=(4, 8))
            return

        # Show search panel, hide category scroll
        self._tools_cat_scroll.pack_forget()
        if not self._tools_search_panel.winfo_ismapped():
            self._tools_search_panel.pack(fill="both", expand=True, padx=10, pady=(4, 8))

        # Clear previous results
        for w in self._tools_search_panel.winfo_children():
            w.destroy()

        if not TOOLKIT_AVAILABLE:
            ctk.CTkLabel(self._tools_search_panel, text="Toolkit not loaded.",
                         font=("Segoe UI", 12), text_color="#666").pack(pady=10)
            return

        reg = get_registry()
        results = reg.search_tools(query)

        if not results:
            ctk.CTkLabel(
                self._tools_search_panel,
                text=f"No functions found matching \"{query}\"",
                font=("Segoe UI", 12), text_color="#666"
            ).pack(pady=20)
            return

        ctk.CTkLabel(
            self._tools_search_panel,
            text=f"  {len(results)} result(s) for \"{query}\"",
            font=("Segoe UI", 11, "bold"), text_color="#34d399"
        ).pack(anchor="w", padx=8, pady=(6, 4))

        for idx, t in enumerate(results[:100]):
            bg = "#1a1a2e" if idx % 2 == 0 else "#12121f"
            row = ctk.CTkFrame(self._tools_search_panel, fg_color=bg, corner_radius=4)
            row.pack(fill="x", padx=4, pady=1)

            left = ctk.CTkFrame(row, fg_color="transparent")
            left.pack(side="left", fill="x", expand=True, padx=8, pady=4)

            cat = t.get("category", "")
            cat_color = CATEGORY_INFO.get(cat, {}).get("color", "#888")

            name_lbl = ctk.CTkLabel(
                left, text=t["name"], font=("Segoe UI", 11, "bold"),
                text_color="#c0c0e0", anchor="w", cursor="hand2"
            )
            name_lbl.pack(anchor="w")
            name_lbl.bind("<Button-1>", lambda e, tool=t: self._show_tool_detail(tool))

            ctk.CTkLabel(
                left, text=f"[{cat}]  {(t.get('doc') or '')[:80]}",
                font=("Segoe UI", 10), text_color="#666", anchor="w"
            ).pack(anchor="w")

            right = ctk.CTkFrame(row, fg_color="transparent")
            right.pack(side="right", padx=6, pady=4)

            ctk.CTkButton(
                right, text="Copy", width=50, height=22,
                font=("Segoe UI", 10), fg_color="#2a2a3a", hover_color="#3a3a4a",
                command=lambda tn=t["name"]: self._copy_to_clipboard(tn)
            ).pack(side="right", padx=(4, 0))

            ctk.CTkButton(
                right, text="Run", width=44, height=22,
                font=("Segoe UI", 10, "bold"), fg_color="#2563eb", hover_color="#1d4ed8",
                command=lambda tn=t["name"], td=t.get("doc", ""): self._run_tool_prompt(tn, td)
            ).pack(side="right")

    def _clear_tools_search(self):
        self.tools_search_var.set("")
        self._tools_search_entry.focus()

    def _try_capability(self, example_prompt):
        self.tabview.set("Agent")
        self.input_box.delete("1.0", "end")
        self.input_box.insert("1.0", example_prompt)
        self._add_system_msg(f"Loaded example: {example_prompt}\nHit Run to try it.")

    def _copy_tool_json(self, tool_name):
        if not TOOLKIT_AVAILABLE:
            return
        reg = get_registry()
        info = reg.get_tool_info(tool_name)
        if not info:
            self._copy_to_clipboard(tool_name)
            return
        args = {}
        for pname, pinfo in info.get("params", {}).items():
            if pinfo.get("required"):
                args[pname] = f"<{pinfo['type']}>"
            elif pinfo.get("default") is not None:
                args[pname] = pinfo["default"]
        example = json.dumps({
            "action": "tool_call",
            "tool": tool_name,
            "args": args,
            "reason": (info.get("doc") or "")[:50]
        }, indent=2)
        self._copy_to_clipboard(example)

    def _save_current_task(self):
        prompt = self.input_box.get("1.0", "end").strip()
        if not prompt:
            self._add_error_msg("Nothing to save. Type a task first.")
            return

        # Ask for a name via popup
        dialog = ctk.CTkInputDialog(text="Name for this task:", title="Save Task")
        name = dialog.get_input()
        if not name:
            return

        self.saved_tasks.append({
            "name": name,
            "prompt": prompt,
            "created": datetime.now().isoformat(),
        })
        save_json(SAVED_TASKS_FILE, self.saved_tasks)
        self._refresh_saved()
        self._add_system_msg(f"Task saved: {name}")

    def _load_saved_task(self, prompt):
        self.tabview.set("Agent")
        self.input_box.delete("1.0", "end")
        self.input_box.insert("1.0", prompt)

    def _delete_saved_task(self, idx):
        if 0 <= idx < len(self.saved_tasks):
            removed = self.saved_tasks.pop(idx)
            save_json(SAVED_TASKS_FILE, self.saved_tasks)
            self._refresh_saved()

    # ── AI Coder Tab ──

    # Tool registry: each tool the user has installed
    _CODER_TOOLS = [
        # ── Code Generation ──
        {
            "name": "Gemini Coder",
            "desc": "Task-driven code generation with time budgets, iteration tracking, and auto-improve. "
                    "Define a coding task, set a time limit, and let Gemini iterate until it's done.",
            "category": "Code Generation",
            "model": "Google Gemini",
            "color": "#2563eb",
            "launch": "pythonw gemini_coder/launch.pyw",
            "cwd": True,
        },
        {
            "name": "PhantomForge",
            "desc": "Headless app builder using local models. Supports Deepseek-Coder, CodeLlama, "
                    "Qwen — fully offline. Multi-step reasoning, project generation, MoE routing.",
            "category": "Code Generation",
            "model": "Ollama (Deepseek/Qwen/CodeLlama)",
            "color": "#7c3aed",
            "launch": "pythonw -m phantom_forge --mode gui",
            "cwd": True,
        },
        {
            "name": "Vibe Coder",
            "desc": "3-agent local pipeline: Planner designs the architecture, Coder writes it, "
                    "Reviewer checks for bugs. 100%% offline with Ollama.",
            "category": "Code Generation",
            "model": "Ollama (local)",
            "color": "#ec4899",
            "launch": "streamlit run vibe_coder/app.py",
            "cwd": True,
        },
        # ── GUI & UI Building ──
        {
            "name": "GUI Builder",
            "desc": "Generate complete Python GUI apps from natural language. Supports Tkinter, "
                    "PyQt, wxPython. Live preview, template library, multi-file projects.",
            "category": "GUI & UI Building",
            "model": "Google Gemini",
            "color": "#10b981",
            "launch": "python -m gui_builder",
            "cwd": True,
        },
        # ── Browser AI Orchestration ──
        {
            "name": "Autocoder (Web)",
            "desc": "Multi-browser orchestration via Chrome DevTools Protocol. Send prompts to "
                    "ChatGPT, Claude, Gemini web — simultaneously. Direct DOM control, no pixel guessing.",
            "category": "Browser AI Orchestration",
            "model": "Any web AI (ChatGPT, Claude, Gemini)",
            "color": "#f59e0b",
            "launch": "pythonw gemini_coder_web/launch.pyw",
            "cwd": True,
        },
        # ── Prompt Engineering ──
        {
            "name": "Prompt Architect",
            "desc": "Structured prompt engineering workbench. DEPTH + SCoT framework. Build perfect "
                    "system prompts with persona, cognition, constraints, and output format.",
            "category": "Prompt Engineering",
            "model": "Framework-agnostic (any LLM)",
            "color": "#06b6d4",
            "launch": "python prompt_architect.py",
            "cwd": True,
        },
        # ── Local Model Infrastructure ──
        {
            "name": "Local Hub (MoE Router)",
            "desc": "Intelligent model router — classifies your prompt and picks the best local model "
                    "(Qwen, Mistral, Dolphin, etc.). Chat interface with system telemetry.",
            "category": "Local Model Infrastructure",
            "model": "Ollama (multi-model MoE)",
            "color": "#64748b",
            "launch": "streamlit run local_hub/app.py",
            "cwd": True,
        },
        {
            "name": "Local Relay",
            "desc": "Hybrid code analysis pipeline. Routes between local Qwen (summaries, function "
                    "detection) and Claude to minimize token usage. Cost-efficient coding.",
            "category": "Local Model Infrastructure",
            "model": "Qwen 2.5 7B + Claude",
            "color": "#64748b",
            "launch": "python local_relay/local_relay.py",
            "cwd": True,
        },
        # ── Analysis & Extraction ──
        {
            "name": "Gemini Analyzer",
            "desc": "Parse Google Gemini takeout exports. Categorize conversations, extract code "
                    "snippets, identify projects. Recover code from past Gemini sessions.",
            "category": "Analysis & Extraction",
            "model": "Gemini export reader",
            "color": "#ef4444",
            "launch": "python gemini_analyzer/main.py",
            "cwd": True,
        },
        # ── Context & Token Management ──
        {
            "name": "Claude Token Saver",
            "desc": "Pre-build project context so Claude doesn't rescan every session. "
                    "Bootstrap generates CLAUDE.md, memory files, and snippet libraries. "
                    "Delta updates keep context fresh. Tracks cumulative token savings.",
            "category": "Context & Token Management",
            "model": "Claude / any LLM",
            "color": "#a78bfa",
            "launch": "python -m claude_backend.gui",
            "cwd_override": "claude interaction tool",
        },
    ]

    # Quick-start options that route to the right tool
    _QUICK_START = [
        {
            "label": "Build an app with AI (cloud)",
            "desc": "Use Gemini to generate a full application from a description",
            "tool": "Gemini Coder",
            "color": "#2563eb",
        },
        {
            "label": "Build an app offline (local)",
            "desc": "Use Deepseek/CodeLlama via Ollama — no internet needed",
            "tool": "PhantomForge",
            "color": "#7c3aed",
        },
        {
            "label": "Generate a GUI from text",
            "desc": "Describe a UI and get working Tkinter/PyQt code with live preview",
            "tool": "GUI Builder",
            "color": "#10b981",
        },
        {
            "label": "Orchestrate web AI models",
            "desc": "Control ChatGPT, Claude, Gemini web simultaneously via Chrome",
            "tool": "Autocoder (Web)",
            "color": "#f59e0b",
        },
        {
            "label": "Craft the perfect prompt",
            "desc": "Engineer structured system prompts with DEPTH + SCoT framework",
            "tool": "Prompt Architect",
            "color": "#06b6d4",
        },
        {
            "label": "Vibe code with local agents",
            "desc": "Planner → Coder → Reviewer pipeline, fully offline",
            "tool": "Vibe Coder",
            "color": "#ec4899",
        },
        {
            "label": "Save tokens & build context",
            "desc": "Pre-scan a project so Claude skips the expensive rescan every time",
            "tool": "Claude Token Saver",
            "color": "#a78bfa",
        },
    ]

    @staticmethod
    def _bind_mousewheel(scrollable_frame):
        """Propagate mouse-wheel scroll to a CTkScrollableFrame from all children."""
        canvas = None
        for child in scrollable_frame.winfo_children():
            if hasattr(child, '_parent_canvas'):
                canvas = child._parent_canvas
                break
        if canvas is None:
            # CTkScrollableFrame stores canvas as _parent_canvas on its inner frame
            canvas = getattr(scrollable_frame, '_parent_canvas', None)
        if canvas is None:
            return

        def _on_wheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _bind_all(widget):
            widget.bind("<MouseWheel>", _on_wheel, add="+")
            for child in widget.winfo_children():
                _bind_all(child)

        _bind_all(scrollable_frame)

    def _build_coder_tab(self):
        scroll = ctk.CTkScrollableFrame(self.tab_coder, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # ── Header ──
        hdr = ctk.CTkFrame(scroll, fg_color="#1e1e2e", corner_radius=0)
        hdr.pack(fill="x", padx=0, pady=0)
        hi = ctk.CTkFrame(hdr, fg_color="transparent")
        hi.pack(fill="x", padx=14, pady=(10, 8))
        ctk.CTkLabel(hi, text="AI Coder", font=("Segoe UI", 18, "bold")).pack(side="left")
        ctk.CTkLabel(hi, text=f"{len(self._CODER_TOOLS)} tools  |  local + cloud",
                     font=("Segoe UI", 11), text_color="#34d399").pack(side="right")

        # ── Quick Start: What do you want to do? ──
        qs_sec = ctk.CTkFrame(scroll, fg_color="#1e1e2e", corner_radius=10)
        qs_sec.pack(fill="x", padx=10, pady=(8, 4))

        qs_hdr = ctk.CTkFrame(qs_sec, fg_color="transparent")
        qs_hdr.pack(fill="x", padx=10, pady=(8, 4))
        ctk.CTkLabel(qs_hdr, text="", width=5, height=24, fg_color="#22c55e",
                     corner_radius=3).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(qs_hdr, text="Quick Start — What do you want to do?",
                     font=("Segoe UI", 14, "bold")).pack(side="left")

        for qs in self._QUICK_START:
            row = ctk.CTkFrame(qs_sec, fg_color="#0f0f1a", corner_radius=8)
            row.pack(fill="x", padx=10, pady=3)
            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x", padx=10, pady=(8, 2))
            ctk.CTkLabel(top, text=qs["label"], font=("Segoe UI", 13, "bold"),
                         text_color="#e0e0e0").pack(side="left")
            ctk.CTkButton(
                top, text="Launch", width=70, height=26,
                font=("Segoe UI", 11, "bold"), fg_color=qs["color"],
                hover_color="#444",
                command=lambda t=qs["tool"]: self._launch_coder_tool(t),
            ).pack(side="right")
            ctk.CTkLabel(row, text=qs["desc"], font=("Segoe UI", 11),
                         text_color="#999", anchor="w", wraplength=620,
                         ).pack(fill="x", padx=10, pady=(0, 8))

        # Spacer
        ctk.CTkFrame(scroll, height=4, fg_color="transparent").pack(fill="x")

        # ── Full Tool Cards by Category ──
        cats_seen = []
        for tool in self._CODER_TOOLS:
            cat = tool["category"]
            if cat not in cats_seen:
                cats_seen.append(cat)

        for cat in cats_seen:
            cat_tools = [t for t in self._CODER_TOOLS if t["category"] == cat]
            cat_color = cat_tools[0]["color"]

            sec = ctk.CTkFrame(scroll, fg_color="#1e1e2e", corner_radius=10)
            sec.pack(fill="x", padx=10, pady=4)

            ch = ctk.CTkFrame(sec, fg_color="transparent")
            ch.pack(fill="x", padx=10, pady=(8, 4))
            ctk.CTkLabel(ch, text="", width=5, height=24, fg_color=cat_color,
                         corner_radius=3).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(ch, text=cat, font=("Segoe UI", 14, "bold")).pack(side="left")
            ctk.CTkLabel(ch, text=f"{len(cat_tools)} tool{'s' if len(cat_tools) > 1 else ''}",
                         font=("Segoe UI", 11), text_color="#888", fg_color="#0f0f1a",
                         corner_radius=5, width=55).pack(side="left", padx=(8, 0))

            for tool in cat_tools:
                card = ctk.CTkFrame(sec, fg_color="#0f0f1a", corner_radius=8)
                card.pack(fill="x", padx=10, pady=3)

                top = ctk.CTkFrame(card, fg_color="transparent")
                top.pack(fill="x", padx=10, pady=(8, 2))

                ctk.CTkLabel(top, text=tool["name"], font=("Segoe UI", 13, "bold"),
                             text_color="#e0e0e0").pack(side="left")

                ctk.CTkButton(
                    top, text="Launch", width=70, height=26,
                    font=("Segoe UI", 11, "bold"), fg_color=tool["color"],
                    hover_color="#444",
                    command=lambda t=tool["name"]: self._launch_coder_tool(t),
                ).pack(side="right", padx=(4, 0))

                ctk.CTkButton(
                    top, text="Copy Cmd", width=70, height=26,
                    font=("Segoe UI", 10), fg_color="#2a2a3a", hover_color="#3a3a4a",
                    command=lambda t=tool: self._copy_to_clipboard(t["launch"]),
                ).pack(side="right", padx=(4, 0))

                # Model badge
                ctk.CTkLabel(top, text=tool["model"], font=("Segoe UI", 10),
                             text_color="#888", fg_color="#1a1a2e",
                             corner_radius=4).pack(side="right", padx=(0, 8))

                ctk.CTkLabel(card, text=tool["desc"], font=("Segoe UI", 11),
                             text_color="#999", anchor="w", justify="left",
                             wraplength=620).pack(fill="x", padx=10, pady=(0, 8))

        # ── Launch Log ──
        log_hdr = ctk.CTkFrame(scroll, fg_color="transparent")
        log_hdr.pack(fill="x", padx=10, pady=(8, 2))
        ctk.CTkLabel(log_hdr, text="Launch Log",
                     font=("Segoe UI", 14, "bold")).pack(side="left")
        ctk.CTkButton(log_hdr, text="Clear", width=60, height=26,
                       font=("Segoe UI", 11), fg_color="#555555", hover_color="#666666",
                       command=self._coder_clear_log).pack(side="right")

        self._coder_log = ctk.CTkScrollableFrame(scroll, fg_color="#1a1a1a",
                                                   corner_radius=10, height=120)
        self._coder_log.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        # Fix scrolling on all child widgets
        self.tab_coder.after(200, lambda: self._bind_mousewheel(scroll))

    def _launch_coder_tool(self, tool_name):
        """Find and launch a coder tool by name."""
        tool = None
        for t in self._CODER_TOOLS:
            if t["name"] == tool_name:
                tool = t
                break
        if not tool:
            self._coder_log_msg("ERROR", f"Tool '{tool_name}' not found", "#f87171")
            return

        ai_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        cwd = ai_dir
        if "cwd_override" in tool:
            cwd = os.path.join(ai_dir, tool["cwd_override"])
        cmd = tool["launch"]

        pid, msg = self._proc_mgr.launch(tool_name, cmd, cwd)
        if pid and "already running" in msg:
            self._coder_log_msg("WARN", msg, "#ca8a04")
        elif pid:
            self._coder_log_msg("LAUNCH", f"{tool['name']}  PID {pid}  ({cmd})", tool["color"])
        else:
            self._coder_log_msg("ERROR", msg, "#f87171")

    def _coder_log_msg(self, sender, text, color="#e0e0e0"):
        frame = ctk.CTkFrame(self._coder_log, fg_color="transparent")
        frame.pack(fill="x", padx=5, pady=2, anchor="w")
        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text=sender, font=("Segoe UI", 10, "bold"),
                     text_color=color, anchor="w").pack(side="left")
        ctk.CTkButton(top, text="cp", width=28, height=16, font=("Segoe UI", 9),
                      fg_color="#333333", hover_color="#444444", corner_radius=3,
                      command=lambda: self._copy_to_clipboard(text)).pack(side="right")
        ctk.CTkLabel(frame, text=text, font=("Segoe UI", 12), text_color="#cccccc",
                     anchor="w", justify="left", wraplength=650
                     ).pack(anchor="w", padx=(8, 0))

    def _coder_clear_log(self):
        for w in self._coder_log.winfo_children():
            w.destroy()

    # ── Clipboard Image Tools Tab ──
    def _build_clipboard_tab(self):
        ACCENT = "#f59e0b"
        ACCENT_HOVER = "#d97706"

        scroll = ctk.CTkScrollableFrame(self.tab_clipboard, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # ── Header ──
        hdr_frame = ctk.CTkFrame(scroll, fg_color="#1e1e2e", corner_radius=0)
        hdr_frame.pack(fill="x", padx=0, pady=0)
        hdr_inner = ctk.CTkFrame(hdr_frame, fg_color="transparent")
        hdr_inner.pack(fill="x", padx=14, pady=(10, 8))
        ctk.CTkLabel(hdr_inner, text="Clipboard Image Tools",
                     font=("Segoe UI", 18, "bold")).pack(side="left")
        ctk.CTkLabel(hdr_inner, text="17 functions  |  in-place image editing",
                     font=("Segoe UI", 11), text_color="#34d399").pack(side="right")

        # ── Status Bar ──
        status_sec = ctk.CTkFrame(scroll, fg_color="#161622", corner_radius=0)
        status_sec.pack(fill="x", padx=0, pady=0)
        status_inner = ctk.CTkFrame(status_sec, fg_color="transparent")
        status_inner.pack(fill="x", padx=14, pady=8)

        ctk.CTkButton(status_inner, text="Refresh", width=70, height=30,
                       font=("Segoe UI", 12, "bold"), fg_color=ACCENT,
                       hover_color=ACCENT_HOVER, text_color="#000000",
                       command=self._refresh_clipboard_info).pack(side="left")

        self._clip_status_label = ctk.CTkLabel(
            status_inner, text="  No image in clipboard",
            font=("Segoe UI", 12), text_color="#888888")
        self._clip_status_label.pack(side="left", padx=(10, 0))

        # ── Section: Quick Actions ──
        qa_sec = ctk.CTkFrame(scroll, fg_color="#1e1e2e", corner_radius=10)
        qa_sec.pack(fill="x", padx=10, pady=(8, 4))

        qa_hdr = ctk.CTkFrame(qa_sec, fg_color="transparent")
        qa_hdr.pack(fill="x", padx=10, pady=(8, 4))
        ctk.CTkLabel(qa_hdr, text="", width=5, height=24, fg_color=ACCENT,
                     corner_radius=3).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(qa_hdr, text="Quick Actions",
                     font=("Segoe UI", 14, "bold")).pack(side="left")

        # Row 1
        qa_r1 = ctk.CTkFrame(qa_sec, fg_color="transparent")
        qa_r1.pack(fill="x", padx=10, pady=2)

        ctk.CTkButton(qa_r1, text="Check Clipboard", width=120, height=32,
                       font=("Segoe UI", 12), fg_color="#2a2a3a", hover_color="#3a3a4a",
                       command=lambda: self._clip_run("has_image_in_clipboard")
                       ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(qa_r1, text="Create Blank Image", width=130, height=32,
                       font=("Segoe UI", 12), fg_color="#2a2a3a", hover_color="#3a3a4a",
                       command=self._clip_create_blank
                       ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(qa_r1, text="Load from File", width=110, height=32,
                       font=("Segoe UI", 12), fg_color="#2a2a3a", hover_color="#3a3a4a",
                       command=self._clip_load_file
                       ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(qa_r1, text="Save to File", width=100, height=32,
                       font=("Segoe UI", 12), fg_color=ACCENT, hover_color=ACCENT_HOVER,
                       text_color="#000000",
                       command=self._clip_save_file
                       ).pack(side="left", padx=(0, 4))

        # Row 2
        qa_r2 = ctk.CTkFrame(qa_sec, fg_color="transparent")
        qa_r2.pack(fill="x", padx=10, pady=(2, 8))

        ctk.CTkButton(qa_r2, text="Image to Base64", width=120, height=32,
                       font=("Segoe UI", 12), fg_color="#2a2a3a", hover_color="#3a3a4a",
                       command=lambda: self._clip_run("get_clipboard_image_base64")
                       ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(qa_r2, text="Get Image Size", width=110, height=32,
                       font=("Segoe UI", 12), fg_color="#2a2a3a", hover_color="#3a3a4a",
                       command=lambda: self._clip_run("get_clipboard_image_size")
                       ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(qa_r2, text="Average Color", width=110, height=32,
                       font=("Segoe UI", 12), fg_color="#2a2a3a", hover_color="#3a3a4a",
                       command=lambda: self._clip_run("get_clipboard_image_average_color")
                       ).pack(side="left", padx=(0, 4))

        # ── Section: Transform ──
        tr_sec = ctk.CTkFrame(scroll, fg_color="#1e1e2e", corner_radius=10)
        tr_sec.pack(fill="x", padx=10, pady=4)

        tr_hdr = ctk.CTkFrame(tr_sec, fg_color="transparent")
        tr_hdr.pack(fill="x", padx=10, pady=(8, 4))
        ctk.CTkLabel(tr_hdr, text="", width=5, height=24, fg_color="#a855f7",
                     corner_radius=3).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(tr_hdr, text="Transform",
                     font=("Segoe UI", 14, "bold")).pack(side="left")

        # Resize row
        res_row = ctk.CTkFrame(tr_sec, fg_color="transparent")
        res_row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(res_row, text="Resize:", font=("Segoe UI", 12),
                     width=55).pack(side="left")
        ctk.CTkLabel(res_row, text="W", font=("Segoe UI", 11),
                     text_color="#777").pack(side="left", padx=(4, 2))
        self._clip_resize_w = ctk.CTkEntry(res_row, width=60, height=30,
                                            font=("Segoe UI", 12), placeholder_text="640")
        self._clip_resize_w.pack(side="left", padx=(0, 4))
        ctk.CTkLabel(res_row, text="H", font=("Segoe UI", 11),
                     text_color="#777").pack(side="left", padx=(4, 2))
        self._clip_resize_h = ctk.CTkEntry(res_row, width=60, height=30,
                                            font=("Segoe UI", 12), placeholder_text="480")
        self._clip_resize_h.pack(side="left", padx=(0, 6))
        ctk.CTkButton(res_row, text="Resize", width=70, height=30,
                       font=("Segoe UI", 12, "bold"), fg_color="#a855f7",
                       hover_color="#7c3aed",
                       command=self._clip_resize).pack(side="left")

        # Crop row
        crop_row = ctk.CTkFrame(tr_sec, fg_color="transparent")
        crop_row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(crop_row, text="Crop:", font=("Segoe UI", 12),
                     width=55).pack(side="left")
        self._clip_crop_entries = {}
        for label in ["L", "T", "R", "B"]:
            ctk.CTkLabel(crop_row, text=label, font=("Segoe UI", 11),
                         text_color="#777").pack(side="left", padx=(4, 2))
            e = ctk.CTkEntry(crop_row, width=50, height=30,
                              font=("Segoe UI", 12), placeholder_text="0")
            e.pack(side="left", padx=(0, 2))
            self._clip_crop_entries[label] = e
        ctk.CTkButton(crop_row, text="Crop", width=60, height=30,
                       font=("Segoe UI", 12, "bold"), fg_color="#a855f7",
                       hover_color="#7c3aed",
                       command=self._clip_crop).pack(side="left", padx=(6, 0))

        # Rotate row
        rot_row = ctk.CTkFrame(tr_sec, fg_color="transparent")
        rot_row.pack(fill="x", padx=10, pady=2)
        ctk.CTkLabel(rot_row, text="Rotate:", font=("Segoe UI", 12),
                     width=55).pack(side="left")
        self._clip_rotate_deg = ctk.CTkEntry(rot_row, width=60, height=30,
                                              font=("Segoe UI", 12), placeholder_text="90")
        self._clip_rotate_deg.pack(side="left", padx=(4, 4))
        ctk.CTkLabel(rot_row, text="deg", font=("Segoe UI", 11),
                     text_color="#777").pack(side="left", padx=(0, 6))
        ctk.CTkButton(rot_row, text="Rotate", width=70, height=30,
                       font=("Segoe UI", 12, "bold"), fg_color="#a855f7",
                       hover_color="#7c3aed",
                       command=self._clip_rotate).pack(side="left")

        # Flip + Blur row
        fb_row = ctk.CTkFrame(tr_sec, fg_color="transparent")
        fb_row.pack(fill="x", padx=10, pady=(2, 8))
        ctk.CTkButton(fb_row, text="Flip Horizontal", width=110, height=32,
                       font=("Segoe UI", 12), fg_color="#2a2a3a", hover_color="#3a3a4a",
                       command=lambda: self._clip_run("flip_clipboard_image_horizontal")
                       ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(fb_row, text="Flip Vertical", width=100, height=32,
                       font=("Segoe UI", 12), fg_color="#2a2a3a", hover_color="#3a3a4a",
                       command=lambda: self._clip_run("flip_clipboard_image_vertical")
                       ).pack(side="left", padx=(0, 8))

        ctk.CTkLabel(fb_row, text="Blur r=", font=("Segoe UI", 11),
                     text_color="#777").pack(side="left", padx=(8, 2))
        self._clip_blur_r = ctk.CTkEntry(fb_row, width=45, height=30,
                                          font=("Segoe UI", 12), placeholder_text="3")
        self._clip_blur_r.pack(side="left", padx=(0, 4))
        ctk.CTkButton(fb_row, text="Blur", width=60, height=32,
                       font=("Segoe UI", 12, "bold"), fg_color="#a855f7",
                       hover_color="#7c3aed",
                       command=self._clip_blur).pack(side="left")

        # ── Section: Color & Style ──
        cs_sec = ctk.CTkFrame(scroll, fg_color="#1e1e2e", corner_radius=10)
        cs_sec.pack(fill="x", padx=10, pady=4)

        cs_hdr = ctk.CTkFrame(cs_sec, fg_color="transparent")
        cs_hdr.pack(fill="x", padx=10, pady=(8, 4))
        ctk.CTkLabel(cs_hdr, text="", width=5, height=24, fg_color="#ec4899",
                     corner_radius=3).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(cs_hdr, text="Color & Style",
                     font=("Segoe UI", 14, "bold")).pack(side="left")

        # Color buttons row
        cs_r1 = ctk.CTkFrame(cs_sec, fg_color="transparent")
        cs_r1.pack(fill="x", padx=10, pady=2)
        ctk.CTkButton(cs_r1, text="Grayscale", width=90, height=32,
                       font=("Segoe UI", 12), fg_color="#2a2a3a", hover_color="#3a3a4a",
                       command=lambda: self._clip_run("convert_clipboard_image_to_grayscale")
                       ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(cs_r1, text="Invert Colors", width=100, height=32,
                       font=("Segoe UI", 12), fg_color="#2a2a3a", hover_color="#3a3a4a",
                       command=lambda: self._clip_run("invert_clipboard_image_colors")
                       ).pack(side="left", padx=(0, 4))
        ctk.CTkButton(cs_r1, text="Get Average Color", width=130, height=32,
                       font=("Segoe UI", 12), fg_color="#2a2a3a", hover_color="#3a3a4a",
                       command=lambda: self._clip_run("get_clipboard_image_average_color")
                       ).pack(side="left", padx=(0, 4))

        # Border row
        brd_row = ctk.CTkFrame(cs_sec, fg_color="transparent")
        brd_row.pack(fill="x", padx=10, pady=(2, 8))
        ctk.CTkLabel(brd_row, text="Border:", font=("Segoe UI", 12),
                     width=55).pack(side="left")
        ctk.CTkLabel(brd_row, text="Size", font=("Segoe UI", 11),
                     text_color="#777").pack(side="left", padx=(4, 2))
        self._clip_border_size = ctk.CTkEntry(brd_row, width=50, height=30,
                                               font=("Segoe UI", 12), placeholder_text="10")
        self._clip_border_size.pack(side="left", padx=(0, 6))
        ctk.CTkLabel(brd_row, text="Color", font=("Segoe UI", 11),
                     text_color="#777").pack(side="left", padx=(4, 2))
        self._clip_border_color = ctk.CTkEntry(brd_row, width=80, height=30,
                                                font=("Segoe UI", 12), placeholder_text="#000000")
        self._clip_border_color.pack(side="left", padx=(0, 6))
        ctk.CTkButton(brd_row, text="Add Border", width=90, height=30,
                       font=("Segoe UI", 12, "bold"), fg_color="#ec4899",
                       hover_color="#be185d",
                       command=self._clip_add_border).pack(side="left")

        # ── Section: Results Log ──
        log_hdr = ctk.CTkFrame(scroll, fg_color="transparent")
        log_hdr.pack(fill="x", padx=10, pady=(8, 2))
        ctk.CTkLabel(log_hdr, text="Results",
                     font=("Segoe UI", 14, "bold")).pack(side="left")
        ctk.CTkButton(log_hdr, text="Clear", width=60, height=26,
                       font=("Segoe UI", 11), fg_color="#555555", hover_color="#666666",
                       command=self._clip_clear_log).pack(side="right")

        self._clip_log = ctk.CTkScrollableFrame(scroll, fg_color="#1a1a1a",
                                                  corner_radius=10, height=180)
        self._clip_log.pack(fill="both", expand=True, padx=10, pady=(0, 8))

    # ── Clipboard Tab Helpers ──

    def _clip_log_msg(self, sender, text, color="#e0e0e0"):
        """Add a message to the clipboard results log."""
        frame = ctk.CTkFrame(self._clip_log, fg_color="transparent")
        frame.pack(fill="x", padx=5, pady=2, anchor="w")

        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x")

        ctk.CTkLabel(top, text=sender, font=("Segoe UI", 10, "bold"),
                     text_color=color, anchor="w").pack(side="left")

        ctk.CTkButton(top, text="cp", width=28, height=16, font=("Segoe UI", 9),
                      fg_color="#333333", hover_color="#444444", corner_radius=3,
                      command=lambda: self._copy_to_clipboard(text)).pack(side="right")

        ctk.CTkLabel(frame, text=text, font=("Segoe UI", 12), text_color="#cccccc",
                     anchor="w", justify="left", wraplength=650
                     ).pack(anchor="w", padx=(8, 0))

    def _clip_run(self, func_name, kwargs=None):
        """Execute a clipboard_image_tools function and log the result."""
        if not TOOLKIT_AVAILABLE:
            self._clip_log_msg("ERROR", "Toolkit not available", "#f87171")
            return
        import json as _json
        reg = get_registry()
        result = reg.call_tool(f"clipboard_image_tools.{func_name}", kwargs or {})
        ok = result.get("success", False)
        msg = result.get("message", "") or result.get("error", "Unknown result")
        data = result.get("data")

        if ok:
            display = msg
            if data:
                display += f"  |  {_json.dumps(data, default=str)}"
            self._clip_log_msg("OK", display, "#34d399")
        else:
            self._clip_log_msg("ERROR", msg, "#f87171")

        # Auto-refresh status
        self._refresh_clipboard_info()

    def _refresh_clipboard_info(self):
        """Update the clipboard status label with current image info."""
        if not TOOLKIT_AVAILABLE:
            self._clip_status_label.configure(text="  Toolkit not available", text_color="#f87171")
            return
        reg = get_registry()
        has = reg.call_tool("clipboard_image_tools.has_image_in_clipboard")
        if has.get("success") and has.get("data", {}).get("has_image"):
            size = reg.call_tool("clipboard_image_tools.get_clipboard_image_size")
            if size.get("success"):
                w = size["data"]["width"]
                h = size["data"]["height"]
                self._clip_status_label.configure(
                    text=f"  Image: {w} x {h} px", text_color="#34d399")
            else:
                self._clip_status_label.configure(
                    text="  Image present (size unknown)", text_color="#f59e0b")
        else:
            self._clip_status_label.configure(
                text="  No image in clipboard", text_color="#888888")

    def _clip_clear_log(self):
        for w in self._clip_log.winfo_children():
            w.destroy()

    def _clip_create_blank(self):
        self._clip_run("create_blank_image_in_clipboard",
                        {"width": 640, "height": 480, "color": "#FFFFFF"})

    def _clip_load_file(self):
        import tkinter.filedialog as fd
        path = fd.askopenfilename(
            title="Select Image",
            filetypes=[("Images", "*.png *.jpg *.jpeg *.bmp *.gif *.tiff *.webp"),
                       ("All files", "*.*")])
        if path:
            self._clip_run("load_image_to_clipboard", {"filepath": path})

    def _clip_save_file(self):
        import tkinter.filedialog as fd
        path = fd.asksaveasfilename(
            title="Save Clipboard Image",
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("JPEG", "*.jpg"), ("BMP", "*.bmp"),
                       ("All files", "*.*")])
        if path:
            fmt = "PNG"
            if path.lower().endswith((".jpg", ".jpeg")):
                fmt = "JPEG"
            elif path.lower().endswith(".bmp"):
                fmt = "BMP"
            self._clip_run("save_clipboard_image", {"filepath": path, "image_format": fmt})

    def _clip_resize(self):
        try:
            w = int(self._clip_resize_w.get() or "0")
            h = int(self._clip_resize_h.get() or "0")
            if w <= 0 or h <= 0:
                self._clip_log_msg("ERROR", "Enter valid width and height (> 0)", "#f87171")
                return
            self._clip_run("resize_clipboard_image", {"width": w, "height": h})
        except ValueError:
            self._clip_log_msg("ERROR", "Width and height must be integers", "#f87171")

    def _clip_crop(self):
        try:
            vals = {}
            mapping = {"L": "left", "T": "top", "R": "right", "B": "bottom"}
            for label, key in mapping.items():
                vals[key] = int(self._clip_crop_entries[label].get() or "0")
            self._clip_run("crop_clipboard_image", vals)
        except ValueError:
            self._clip_log_msg("ERROR", "Crop values must be integers", "#f87171")

    def _clip_rotate(self):
        try:
            deg = int(self._clip_rotate_deg.get() or "90")
            self._clip_run("rotate_clipboard_image", {"degrees": deg})
        except ValueError:
            self._clip_log_msg("ERROR", "Degrees must be an integer", "#f87171")

    def _clip_blur(self):
        try:
            r = int(self._clip_blur_r.get() or "3")
            if r <= 0:
                self._clip_log_msg("ERROR", "Blur radius must be > 0", "#f87171")
                return
            self._clip_run("blur_clipboard_image", {"radius": r})
        except ValueError:
            self._clip_log_msg("ERROR", "Blur radius must be an integer", "#f87171")

    def _clip_add_border(self):
        try:
            size = int(self._clip_border_size.get() or "10")
            color = self._clip_border_color.get().strip() or "#000000"
            if size <= 0:
                self._clip_log_msg("ERROR", "Border size must be > 0", "#f87171")
                return
            self._clip_run("add_clipboard_image_border",
                            {"border_size": size, "color": color})
        except ValueError:
            self._clip_log_msg("ERROR", "Border size must be an integer", "#f87171")

    # ── Settings Tab ──
    def _build_settings_tab(self):
        scroll = ctk.CTkScrollableFrame(self.tab_settings, fg_color="transparent")
        scroll.pack(fill="both", expand=True)

        # ── Section: Appearance ──
        self._settings_section(scroll, "Appearance", "#3b82f6", [
            ("Theme", "Switch between Dark, Light, and System appearance modes.", self._make_theme_row),
            ("Font Size", "Adjust the base text size for better readability.", self._make_fontsize_row),
        ])

        # ── Section: Tutorials ──
        tut_sec = ctk.CTkFrame(scroll, fg_color="#1e1e2e", corner_radius=10)
        tut_sec.pack(fill="x", padx=15, pady=6)

        tut_hdr = ctk.CTkFrame(tut_sec, fg_color="transparent")
        tut_hdr.pack(fill="x", padx=12, pady=(12, 6))
        ctk.CTkLabel(tut_hdr, text="", width=5, height=22, fg_color="#10b981",
                     corner_radius=3).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(tut_hdr, text="Tutorials & Help", font=("Segoe UI", 16, "bold"),
                     text_color="#10b981").pack(side="left")

        tutorials = [
            ("What is Screen Agent?", "#2563eb", [
                ("Plain English explanation",
                 "Screen Agent is an AI assistant that lives on your computer. It can see your screen — like having eyes — and control your mouse and keyboard — like having hands. You tell it what you want done in plain English, and it figures out the steps by itself."),
                ("Powered by Ollama (local AI, totally private)",
                 "Unlike ChatGPT or other online AI, Screen Agent uses Ollama — a free program that runs AI models directly on your PC. Nothing leaves your computer. No internet required for the AI itself. Your data stays 100% private."),
                ("What makes it powerful",
                 "Beyond just clicking and typing, Screen Agent has access to 3,000+ built-in functions (the 'toolkit'). These let it do things like check your CPU, generate passwords, read text from images, organize files, and much more — often without even looking at the screen."),
            ]),

            ("Getting Started (Step by Step)", "#22c55e", [
                ("Step 1: Make sure Ollama is running",
                 "Ollama is the program that runs the AI. Look for it in your system tray (bottom-right corner). If it's not running, find 'Ollama' in your Start menu and open it. A small icon should appear."),
                ("Step 2: Go to the Agent tab",
                 "Click 'Agent' at the top of Screen Agent. This is the main control panel where you give instructions."),
                ("Step 3: Select a vision model",
                 "In the Model section, choose 'llava:7b' from the dropdown. This is the recommended model — it can see your screen AND use all the toolkit functions. If you don't have it yet, click 'Grab Model' to download it (about 4.7GB, takes a few minutes)."),
                ("Step 4: Click Activate",
                 "Click the green 'Activate' button. Wait 10-30 seconds for the model to load into memory. The button will turn dark green and say 'Active' when ready."),
                ("Step 5: Type what you want or pick an automation",
                 "Either scroll down and click 'Run' on a pre-built automation, OR type your own request in the text box at the top and click 'Run'. Example: 'Check my CPU usage and memory'."),
                ("Step 6: Watch it work",
                 "The agent starts taking steps. Each action appears in the Chat Log. You can pause it with the yellow 'Pause' button, or stop it completely with the red 'Stop' button."),
            ]),

            ("Understanding the Tools Tab", "#a855f7", [
                ("What the Tools tab is",
                 "The Tools tab is a directory of every function the agent can call. Think of them as special abilities — each one does a specific thing. There are 3,000+ of them organized into 22 categories."),
                ("You don't need to know code",
                 "You never need to write or understand code to use these tools. Each one has a plain English description. Just click 'Run' next to any function and the agent will use it for you."),
                ("Browsing categories",
                 "Tools are grouped into categories like 'System' (computer info), 'Files' (file management), 'Security' (passwords), etc. Click 'Show Functions' on any category to see what's inside."),
                ("Searching for a tool",
                 "Use the search bar at the top of the Tools tab to find tools by keyword. Type 'password' to find password tools, 'cpu' for CPU tools, 'rename' for file renaming tools, and so on."),
                ("Using the Run button",
                 "Every function row has a 'Run' button. Clicking it loads a ready-made prompt into the Agent tab's input box. Just click Run in the Agent tab to execute it."),
            ]),

            ("How Automations Work", "#f59e0b", [
                ("Pre-built step sequences",
                 "Automations in the Agent tab are like recipes. Each one is a carefully written set of instructions telling the agent exactly what steps to take to complete a common task. They're tested and reliable."),
                ("Tasks marked with '...'",
                 "Some automations have '...' in their name — this means they need you to fill in a detail first. For example, 'Search the Web ...' needs you to type what to search for. The prompt will be pre-filled with a placeholder for you to replace."),
                ("Long Automations",
                 "The 'Long Automation' category at the top has the most powerful automations. They run 10-20 steps automatically. Great for complex tasks like full system health checks or organizing an entire folder."),
                ("The agent adapts as it goes",
                 "The agent doesn't just follow the script blindly. After each step, it takes a screenshot and looks at what happened. If something unexpected occurs, it adjusts its next action accordingly."),
            ]),

            ("Copy and Paste Tips", "#06b6d4", [
                ("Right-click anywhere for a context menu",
                 "Right-click on the input text box to get Copy, Cut, Paste, Select All, and Clear options. Right-click on any message in the Chat Log to get Copy and Copy & Load options."),
                ("The 'cp' button on messages",
                 "Every message in the Chat Log has a small 'cp' button on the right side of the header. Click it to instantly copy that message's content to your clipboard."),
                ("Copy All Chat Log button",
                 "At the top of the Chat Log section, there's a 'Copy All' button. Click it to copy the entire conversation to your clipboard — great for saving or sharing results."),
                ("Ctrl+A in text boxes",
                 "Click inside the input text box and press Ctrl+A to select all the text. Then Ctrl+C to copy it, or just start typing to replace it."),
                ("Copy buttons in Tools tab",
                 "Every function in the Tools tab has a 'Copy' button that copies the function name. Great for pasting function names into your own prompts."),
            ]),

            ("Emergency Stop", "#ef4444", [
                ("The fastest emergency stop",
                 "If the agent is doing something wrong or you need to stop it immediately: quickly move your mouse to the TOP-LEFT CORNER of your screen. This triggers pyautogui's failsafe and instantly halts all actions."),
                ("The Stop button",
                 "Click the red 'Stop' button to gracefully stop the agent after its current action completes. The agent will finish what it's currently doing and then stop."),
                ("The Pause button",
                 "Click the yellow 'Pause' button to freeze the agent mid-task. It will stop before the next action. Click 'Resume' (same button) to continue from where it stopped."),
                ("Enable 'Confirm actions'",
                 "In the Options section of the Agent tab, check 'Confirm actions'. The agent will ask your permission before executing each action — gives you full control over every step."),
            ]),

            ("Troubleshooting", "#f87171", [
                ("Agent not responding or no models found",
                 "Check that Ollama is running (look in your system tray). Click 'Refresh' in the Model section. If you see 'Ollama error', Ollama may have crashed — restart it from the Start menu."),
                ("Need to download a model",
                 "If your model dropdown is empty, you need to download a model. Select 'llava:7b' in the 'Grab Model' dropdown and click the purple 'Grab Model' button. It downloads automatically."),
                ("Actions look wrong or the agent is confused",
                 "Try being more specific in your task description. Enable 'Confirm actions' to approve each step. Try a different model if available. Lower the screenshot quality to '640px' if the model seems slow."),
                ("Too slow",
                 "Reduce the 'Delay' setting from 1.0 to 0.5 seconds. Change Screenshot quality to '640px (fast)'. These speed things up at the cost of some accuracy."),
                ("App won't start",
                 "Run: uv pip install customtkinter pyautogui pillow ollama mss  in your terminal from the Screen Agent folder."),
            ]),

            ("Keyboard Shortcuts", "#888888", [
                ("Enter = Run",
                 "Press Enter in the input box to instantly start the agent — same as clicking the Run button."),
                ("Shift+Enter = New Line",
                 "Press Shift+Enter to add a line break in your command without starting the agent. Useful for multi-line instructions."),
                ("Ctrl+A = Select All",
                 "In the input box, press Ctrl+A to select all text. Then type to replace it, or Ctrl+C to copy it."),
                ("Right-click = Context Menu",
                 "Right-click on the input box or any chat message for copy/paste options."),
                ("Mouse to Top-Left = Emergency Stop",
                 "Move your mouse very quickly to the absolute top-left corner of your screen to trigger an emergency stop."),
            ]),
        ]

        for section_title, section_color, items in tutorials:
            sec = ctk.CTkFrame(tut_sec, fg_color="#131320", corner_radius=8)
            sec.pack(fill="x", padx=10, pady=4)

            # Collapsible section header
            tsh = ctk.CTkFrame(sec, fg_color="transparent")
            tsh.pack(fill="x", padx=10, pady=(8, 4))
            ctk.CTkLabel(tsh, text="", width=4, height=18, fg_color=section_color,
                         corner_radius=2).pack(side="left", padx=(0, 8))
            ctk.CTkLabel(tsh, text=section_title, font=("Segoe UI", 13, "bold"),
                         text_color=section_color).pack(side="left")

            items_frame = ctk.CTkFrame(sec, fg_color="transparent")

            def make_toggle_tut(frame, items, color):
                frame.pack(fill="x")
                for item_title, item_text in items:
                    item_card = ctk.CTkFrame(frame, fg_color="#1a1a2e", corner_radius=6)
                    item_card.pack(fill="x", padx=10, pady=2)
                    ctk.CTkLabel(item_card, text=item_title, font=("Segoe UI", 11, "bold"),
                                 text_color="#e0e0e0", anchor="w").pack(fill="x", padx=10, pady=(7, 2))
                    ctk.CTkLabel(item_card, text=item_text, font=("Segoe UI", 11),
                                 text_color="#999", anchor="w", justify="left",
                                 wraplength=640).pack(fill="x", padx=10, pady=(0, 7))

            make_toggle_tut(items_frame, items, section_color)

        ctk.CTkLabel(tut_sec, text="", height=6).pack()

        # ── Section: About ──
        about_sec = ctk.CTkFrame(scroll, fg_color="#1e1e2e", corner_radius=10)
        about_sec.pack(fill="x", padx=15, pady=6)

        about_hdr = ctk.CTkFrame(about_sec, fg_color="transparent")
        about_hdr.pack(fill="x", padx=12, pady=(12, 6))
        ctk.CTkLabel(about_hdr, text="", width=5, height=22, fg_color="#64748b",
                     corner_radius=3).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(about_hdr, text="About Screen Agent", font=("Segoe UI", 16, "bold"),
                     text_color="#888").pack(side="left")

        about_items = [
            ("Version", "2.0 — Upgraded Tools Browser Edition"),
            ("AI Backend", "Ollama (local, private, no cloud required)"),
            ("Recommended Model", "llava:7b (vision + text, 4.7GB)"),
            ("Emergency Stop", "Move mouse to top-left corner of screen"),
        ]
        if TOOLKIT_AVAILABLE:
            stats = get_registry().get_stats()
            about_items.insert(2, ("Toolkit Functions", f"{stats['total_tools']:,} functions across {stats['total_modules']} modules in {stats.get('total_categories', 22)} categories"))

        for label, value in about_items:
            row = ctk.CTkFrame(about_sec, fg_color="transparent")
            row.pack(fill="x", padx=14, pady=2)
            ctk.CTkLabel(row, text=f"{label}:", font=("Segoe UI", 12, "bold"),
                         text_color="#888", width=160, anchor="w").pack(side="left")
            ctk.CTkLabel(row, text=value, font=("Segoe UI", 12),
                         text_color="#ccc", anchor="w").pack(side="left")

        ctk.CTkLabel(about_sec, text="", height=8).pack()

        ctk.CTkLabel(scroll, text="Ready to go? Head to the Agent tab and start automating!",
                     font=("Segoe UI", 13, "bold"), text_color="#555").pack(pady=(10, 20))

    def _settings_section(self, parent, title, color, items_with_builders):
        sec = ctk.CTkFrame(parent, fg_color="#1e1e2e", corner_radius=10)
        sec.pack(fill="x", padx=15, pady=6)

        sh = ctk.CTkFrame(sec, fg_color="transparent")
        sh.pack(fill="x", padx=12, pady=(12, 6))
        ctk.CTkLabel(sh, text="", width=5, height=22, fg_color=color,
                     corner_radius=3).pack(side="left", padx=(0, 8))
        ctk.CTkLabel(sh, text=title, font=("Segoe UI", 16, "bold"),
                     text_color=color).pack(side="left")

        for item_title, item_desc, builder in items_with_builders:
            row_card = ctk.CTkFrame(sec, fg_color="#131320", corner_radius=8)
            row_card.pack(fill="x", padx=10, pady=3)

            top = ctk.CTkFrame(row_card, fg_color="transparent")
            top.pack(fill="x", padx=10, pady=(8, 2))

            ctk.CTkLabel(top, text=item_title, font=("Segoe UI", 12, "bold"),
                         text_color="#e0e0e0").pack(side="left")
            builder(top)

            ctk.CTkLabel(row_card, text=item_desc, font=("Segoe UI", 10),
                         text_color="#666", anchor="w").pack(fill="x", padx=10, pady=(0, 8))

        ctk.CTkLabel(sec, text="", height=4).pack()

    def _make_theme_row(self, parent):
        ctk.CTkOptionMenu(
            parent, variable=self.theme_var,
            values=["Dark", "Light", "System"],
            width=120, font=("Segoe UI", 12),
            command=self._change_theme
        ).pack(side="right")

    def _make_fontsize_row(self, parent):
        ctk.CTkLabel(parent, text="(Restart app to apply full change)",
                     font=("Segoe UI", 10), text_color="#555").pack(side="right")

    # ── Clipboard helpers for input box ──
    def _paste_to_input(self):
        try:
            text = self.root.clipboard_get()
            self.input_box.insert("end", text)
        except Exception:
            pass

    def _copy_input(self):
        text = self.input_box.get("1.0", "end").strip()
        if text:
            self._copy_to_clipboard(text)

    # ── Right-click context menus ──
    def _show_input_context_menu(self, event):
        menu = ctk.CTkToplevel(self.root)
        menu.overrideredirect(True)
        menu.attributes("-topmost", True)
        menu.geometry(f"130x165+{event.x_root}+{event.y_root}")
        menu.configure(fg_color="#2a2a3a")

        def close_menu():
            try: menu.destroy()
            except: pass

        def do_copy():
            try:
                sel = self.input_box.get("sel.first", "sel.last")
                if sel:
                    self._copy_to_clipboard(sel)
            except Exception:
                self._copy_input()
            close_menu()

        def do_paste():
            self._paste_to_input()
            close_menu()

        def do_cut():
            try:
                sel = self.input_box.get("sel.first", "sel.last")
                if sel:
                    self._copy_to_clipboard(sel)
                    self.input_box.delete("sel.first", "sel.last")
            except Exception:
                pass
            close_menu()

        def do_select_all():
            self.input_box.tag_add("sel", "1.0", "end")
            close_menu()

        def do_clear():
            self.input_box.delete("1.0", "end")
            close_menu()

        for label, cmd in [("Cut", do_cut), ("Copy", do_copy), ("Paste", do_paste),
                           ("Select All", do_select_all), ("Clear", do_clear)]:
            ctk.CTkButton(menu, text=label, width=120, height=28,
                          font=("Segoe UI", 12), fg_color="#2a2a3a", hover_color="#3a3a4a",
                          anchor="w", command=cmd).pack(padx=4, pady=1)

        menu.focus_set()
        menu.bind("<FocusOut>", lambda e: close_menu())
        menu.bind("<Escape>", lambda e: close_menu())

    def _show_text_context_menu(self, event, text):
        menu = ctk.CTkToplevel(self.root)
        menu.overrideredirect(True)
        menu.attributes("-topmost", True)
        menu.geometry(f"130x70+{event.x_root}+{event.y_root}")
        menu.configure(fg_color="#2a2a3a")

        def close_menu():
            try: menu.destroy()
            except: pass

        ctk.CTkButton(menu, text="Copy", width=120, height=28,
                      font=("Segoe UI", 12), fg_color="#2a2a3a", hover_color="#3a3a4a",
                      anchor="w", command=lambda: (self._copy_to_clipboard(text), close_menu())).pack(padx=4, pady=1)
        ctk.CTkButton(menu, text="Copy & Paste", width=120, height=28,
                      font=("Segoe UI", 12), fg_color="#2a2a3a", hover_color="#3a3a4a",
                      anchor="w", command=lambda: (self._copy_to_clipboard(text), self.input_box.delete("1.0", "end"),
                                                    self.input_box.insert("1.0", text), close_menu())).pack(padx=4, pady=1)

        menu.focus_set()
        menu.bind("<FocusOut>", lambda e: close_menu())
        menu.bind("<Escape>", lambda e: close_menu())

    def _copy_chat_log(self):
        lines = []
        for widget in self.chat_frame.winfo_children():
            for child in widget.winfo_children():
                if isinstance(child, ctk.CTkLabel):
                    t = child.cget("text")
                    if t:
                        lines.append(t)
        self._copy_to_clipboard("\n".join(lines))

    # ── Quick task loader ──
    def _load_quick_task(self, label, desc, prompt):
        self._load_automation(label, desc, prompt, "{query}" in prompt)

    def _load_automation(self, name, desc, prompt, needs_input):
        self.tabview.set("Agent")
        self.input_box.delete("1.0", "end")
        if needs_input:
            self.input_box.insert("1.0", prompt.replace("{query}", ""))
            self._add_system_msg(f"Loaded: {name}\n{desc}\nFill in the details in the text box, then hit Run.")
            self.input_box.focus()
        else:
            self.input_box.insert("1.0", prompt)
            self._add_system_msg(f"Loaded: {name}\n{desc}\nHit Run to start.")

    def _on_enter(self, event):
        if not event.state & 1:
            self._start_agent()
            return "break"

    # ── Chat messages with copy buttons ──
    def _add_msg(self, sender, text, color="#e0e0e0"):
        frame = ctk.CTkFrame(self.chat_frame, fg_color="transparent")
        frame.pack(fill="x", padx=5, pady=2, anchor="w")

        top = ctk.CTkFrame(frame, fg_color="transparent")
        top.pack(fill="x")

        ctk.CTkLabel(top, text=sender, font=("Segoe UI", 10, "bold"), text_color=color, anchor="w").pack(side="left")

        # Copy button on every message
        ctk.CTkButton(top, text="cp", width=28, height=16, font=("Segoe UI", 9),
                      fg_color="#333333", hover_color="#444444", corner_radius=3,
                      command=lambda: self._copy_to_clipboard(text)).pack(side="right")

        msg_label = ctk.CTkLabel(frame, text=text, font=("Segoe UI", 12), text_color="#cccccc",
                     anchor="w", justify="left", wraplength=650)
        msg_label.pack(anchor="w", padx=(8, 0))
        msg_label.bind("<Button-3>", lambda e, t=text: self._show_text_context_menu(e, t))

    def _add_system_msg(self, text): self._add_msg("SYSTEM", text, "#888888")
    def _add_user_msg(self, text): self._add_msg("YOU", text, "#60a5fa")
    def _add_agent_msg(self, text): self._add_msg("AGENT", text, "#34d399")
    def _add_action_msg(self, text): self._add_msg("ACTION", text, "#fbbf24")
    def _add_error_msg(self, text): self._add_msg("ERROR", text, "#f87171")

    def _set_status(self, text, color="#888888"):
        self.status_label.configure(text=text)
        self.status_dot.configure(fg_color=color)

    def _clear_chat(self):
        for w in self.chat_frame.winfo_children():
            w.destroy()
        self.action_history.clear()
        self._add_system_msg("Chat cleared.")

    # ══════════════════════════════════════════════════════════════════════
    #  Model management
    # ══════════════════════════════════════════════════════════════════════
    def _detect_models(self):
        def detect():
            try:
                result = ollama.list()
                vision, all_m = [], []
                model_list = result.models if hasattr(result, 'models') else result.get("models", [])
                for m in model_list:
                    name = m.model if hasattr(m, 'model') else m.get("name", "")
                    all_m.append(name)
                    if any(v in name.lower() for v in ["llava", "vision", "moondream", "bakllava", "minicpm-v"]):
                        vision.append(name)
                self.available_models = vision or all_m
                def ui():
                    models = vision or all_m
                    if models:
                        self.model_dropdown.configure(values=models)
                        self.model_var.set(models[0])
                        self.activate_btn.configure(state="normal")
                        if vision:
                            self._add_system_msg(f"Vision model(s): {', '.join(vision)}")
                        else:
                            self._add_system_msg("No vision models. Grab one or try text model (limited).")
                    else:
                        self._add_error_msg("No Ollama models. Is Ollama running?")
                self.root.after(0, ui)
            except Exception as e:
                err_msg = f"Ollama error: {e}"
                self.root.after(0, lambda m=err_msg: self._add_error_msg(m))
        threading.Thread(target=detect, daemon=True).start()

    def _activate_model(self):
        model = self.model_var.get()
        if not model or model == "Detecting...":
            return
        self.activate_btn.configure(state="disabled", text="Loading...")
        self._add_system_msg(f"Activating {model}...")
        def warmup():
            try:
                ollama.chat(model=model, messages=[{"role": "user", "content": "Hi"}], options={"num_predict": 1})
                self.model_loaded = True
                self.selected_model = model
                self._settings.update("model", model)
                def done():
                    self.activate_btn.configure(text="Active", fg_color="#16a34a")
                    self.model_status_label.configure(text=f"{model} loaded", text_color="#34d399")
                    self._add_system_msg(f"{model} active and ready!")
                self.root.after(0, done)
            except Exception as e:
                err_msg = f"Activate failed: {e}"
                self.root.after(0, lambda: self.activate_btn.configure(state="normal", text="Activate"))
                self.root.after(0, lambda m=err_msg: self._add_error_msg(m))
        threading.Thread(target=warmup, daemon=True).start()

    def _pull_model(self):
        name = self.grab_var.get()
        self.pull_btn.configure(state="disabled", text="Pulling...")
        self._add_system_msg(f"Downloading {name}...")
        def pull():
            try:
                for p in ollama.pull(name, stream=True):
                    st = getattr(p, 'status', '') or ''
                    if "pulling" in st:
                        total = getattr(p, 'total', None)
                        done = getattr(p, 'completed', None)
                        if total and done and total > 0:
                            pct = int(done / total * 100)
                            self.root.after(0, lambda v=pct: self.pull_btn.configure(text=f"Pulling {v}%"))
                self.root.after(0, lambda: self._add_system_msg(f"{name} downloaded! Refresh & Activate."))
                self.root.after(0, lambda: self.pull_btn.configure(state="normal", text="Grab Model"))
                self.root.after(0, self._detect_models)
            except Exception as e:
                err_msg = f"Pull failed: {e}"
                self.root.after(0, lambda m=err_msg: self._add_error_msg(m))
                self.root.after(0, lambda: self.pull_btn.configure(state="normal", text="Grab Model"))
        threading.Thread(target=pull, daemon=True).start()

    # ══════════════════════════════════════════════════════════════════════
    #  Agent core
    # ══════════════════════════════════════════════════════════════════════
    def _capture_screen(self):
        # Create a fresh mss instance per call - mss is NOT thread-safe
        # and self.sct was created in the main thread
        with mss.mss() as sct:
            monitor = sct.monitors[0]
            ss = sct.grab(monitor)
            img = Image.frombytes("RGB", ss.size, ss.bgra, "raw", "BGRX")
            q = self.quality_var.get()
            max_w = 640 if "640" in q else 1280 if "1280" in q else 1920 if "1920" in q else img.width
            if img.width > max_w:
                r = max_w / img.width
                img = img.resize((max_w, int(img.height * r)), Image.LANCZOS)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()

    @staticmethod
    def _fix_json_backslashes(s):
        """Escape lone backslashes that aren't valid JSON escape sequences."""
        valid_after = set('"\\\/bfnrtu')
        result = []
        i = 0
        while i < len(s):
            ch = s[i]
            if ch == "\\" and i + 1 < len(s):
                nxt = s[i + 1]
                if nxt in valid_after:
                    result.append(ch)
                    result.append(nxt)
                    i += 2
                else:
                    result.append("\\\\")
                    i += 1
            else:
                result.append(ch)
                i += 1
        return "".join(result)

    def _parse_action(self, text):
        text = text.strip()
        # Strip markdown code fences (```json ... ``` or ``` ... ```)
        text = re.sub(r'^```(?:json)?\s*', '', text, flags=re.MULTILINE)
        text = re.sub(r'```\s*$', '', text, flags=re.MULTILINE)
        text = text.strip()

        parsed = None

        # 1) Try the whole text as JSON first (raw, then with backslash fix)
        for attempt in [text, self._fix_json_backslashes(text)]:
            try:
                parsed = json.loads(attempt)
                break
            except (json.JSONDecodeError, ValueError):
                pass

        # 2) Find the outermost { ... } block (supports nested braces)
        if parsed is None:
            depth = 0
            start = -1
            for i, ch in enumerate(text):
                if ch == '{':
                    if depth == 0:
                        start = i
                    depth += 1
                elif ch == '}':
                    depth -= 1
                    if depth == 0 and start >= 0:
                        chunk = text[start:i + 1]
                        for attempt in [chunk, self._fix_json_backslashes(chunk)]:
                            try:
                                parsed = json.loads(attempt)
                                break
                            except (json.JSONDecodeError, ValueError):
                                pass
                        if parsed:
                            break
                        start = -1

        # 3) Fallback: flat (non-nested) regex for simple actions
        if parsed is None:
            m = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if m:
                try:
                    parsed = json.loads(m.group())
                except (json.JSONDecodeError, ValueError):
                    pass

        # Reject empty or actionless JSON
        if parsed is None or not parsed or "action" not in parsed:
            return {"action": "think", "thought": text if text else "(model returned empty response)", "reason": "Could not parse valid action"}
        return parsed

    def _execute_action(self, ad):
        action = ad.get("action", "think")
        reason = ad.get("reason", "")

        if action == "click":
            x, y = int(ad["x"]), int(ad["y"])
            btn = ad.get("button", "left")
            self._add_action_msg(f"Click ({btn}) at ({x},{y}) - {reason}")
            pyautogui.click(x, y, button=btn)
        elif action == "double_click":
            x, y = int(ad["x"]), int(ad["y"])
            self._add_action_msg(f"Double-click ({x},{y}) - {reason}")
            pyautogui.doubleClick(x, y)
        elif action == "right_click":
            x, y = int(ad["x"]), int(ad["y"])
            self._add_action_msg(f"Right-click ({x},{y}) - {reason}")
            pyautogui.rightClick(x, y)
        elif action == "type":
            t = ad.get("text", "")
            self._add_action_msg(f"Type: '{t[:50]}' - {reason}")
            pyautogui.typewrite(t, interval=0.02) if t.isascii() else pyautogui.write(t)
        elif action == "key":
            k = ad.get("key", "")
            self._add_action_msg(f"Key: {k} - {reason}")
            pyautogui.press(k)
        elif action == "hotkey":
            keys = ad.get("keys", [])
            self._add_action_msg(f"Hotkey: {'+'.join(keys)} - {reason}")
            pyautogui.hotkey(*keys)
        elif action == "scroll":
            x = int(ad.get("x", self.screen_width // 2))
            y = int(ad.get("y", self.screen_height // 2))
            amt = int(ad.get("amount", -3))
            self._add_action_msg(f"Scroll {amt} at ({x},{y}) - {reason}")
            pyautogui.scroll(amt, x, y)
        elif action == "move":
            x, y = int(ad["x"]), int(ad["y"])
            self._add_action_msg(f"Move to ({x},{y}) - {reason}")
            pyautogui.moveTo(x, y, duration=0.3)
        elif action == "wait":
            s = float(ad.get("seconds", 1))
            self._add_action_msg(f"Wait {s}s - {reason}")
            time.sleep(s)
        elif action == "tool_call":
            tool_name = ad.get("tool", "")
            tool_args = ad.get("args", {})
            self._add_action_msg(f"Tool: {tool_name}({json.dumps(tool_args, default=str)[:80]}) - {reason}")
            if TOOLKIT_AVAILABLE:
                reg = get_registry()

                # ── Security Gate: confirm dangerous write operations ──
                blocked = False
                if self.confirm_var.get():
                    info = reg.get_tool_info(tool_name)
                    if info:
                        cat = info.get("category", "")
                        func_name = info.get("function", "")
                        is_read_only = any(func_name.startswith(p) for p in SAFE_PREFIXES)
                        if cat in DANGEROUS_CATEGORIES and not is_read_only:
                            self._waiting_confirm = True
                            self._confirm_denied = False
                            desc = f"{tool_name}({json.dumps(tool_args, default=str)[:120]})"
                            self.root.after(0, lambda d=desc: self._ask_confirm_tool(d))
                            while self._waiting_confirm and self.running:
                                time.sleep(0.15)
                            if self._confirm_denied:
                                self._add_msg("BLOCKED", f"User denied: {tool_name}", "#f87171")
                                self._last_tool_result = '{"success": false, "error": "User denied permission"}'
                                blocked = True

                if not blocked:
                    result = reg.call_tool(tool_name, tool_args)
                    result_str = json.dumps(result, default=str, indent=2)
                    if len(result_str) > 500:
                        result_str = result_str[:500] + "..."
                    self._add_msg("TOOL RESULT", result_str, "#a78bfa")
                    self._last_tool_result = result_str
            else:
                self._add_error_msg("Toolkit not available")
        elif action == "think":
            self._add_agent_msg(f"Thinking: {ad.get('thought', reason)}")
        elif action == "done":
            self._add_agent_msg(f"Done: {reason}")
            return False
        else:
            self._add_error_msg(f"Unknown action: {action}")
        return True

    def _agent_loop(self, task):
        self.running = True
        self.action_history = []
        model = self.model_var.get()
        try: max_steps = int(self.steps_var.get())
        except ValueError: max_steps = 50
        try: delay = float(self.delay_var.get())
        except ValueError: delay = 1.0

        # Build a SHORT tool summary - small models choke on huge prompts
        tools_summary = "browser_control (cdp_connect_tab/cdp_click/cdp_type/cdp_get_text/cdp_navigate/cdp_get_page_text/cdp_get_form_fields/cdp_fill_form/cdp_run_js/cdp_get_links/cdp_launch_chrome — control browser by CSS selector), window_control (win_list_windows/win_find_window/win_get_controls/win_click_button/win_type_in_field/win_get_text/win_select_menu/win_focus_window/win_send_keys — control desktop apps by element name), system_monitor (CPU/memory/disk/processes), process_manager (run commands/kill), text_processing (word count/extract), encryption_actions (passwords/hashes), clipboard_advanced (copy/paste), compression_actions (zip/extract), auto_system_cleaner (temp/cache cleanup), auto_file_organizer (sort files by type), image_processing (resize/crop), desktop_control (wallpaper/dark mode/taskbar), display_gamma (brightness/color temp), wifi_tools (wifi passwords/profiles)"
        system = SYSTEM_PROMPT.format(width=self.screen_width, height=self.screen_height, tools=tools_summary)
        self._last_tool_result = None
        self.root.after(0, lambda: self._set_status("Running", "#22c55e"))
        status = "completed"
        retries = 0
        max_retries = 3

        for step in range(max_steps):
            if not self.running: status = "stopped"; break
            while self.paused and self.running: time.sleep(0.2)
            if not self.running: status = "stopped"; break

            self.root.after(0, lambda s=step: self._set_status(f"Step {s+1}/{max_steps}", "#22c55e"))

            # ── Screenshot — skip when last action was a deterministic tool_call ──
            needs_screenshot = True
            if self.action_history:
                last = self.action_history[-1]
                if "tool:" in last.lower() or "tool_call:" in last.lower():
                    needs_screenshot = False
            # Always screenshot on step 0 so the model can orient
            if step == 0:
                needs_screenshot = True

            ss = None
            if needs_screenshot:
                for attempt in range(2):
                    try:
                        ss = self._capture_screen()
                        break
                    except Exception as e:
                        if attempt == 0:
                            err_msg = f"Screenshot attempt 1 failed: {e}. Retrying..."
                            self.root.after(0, lambda m=err_msg: self._add_error_msg(m))
                            time.sleep(0.5)
                        else:
                            err_msg = f"Screenshot failed twice: {e}. Switching to text-only mode."
                            self.root.after(0, lambda m=err_msg: self._add_error_msg(m))

            hist = ""
            if self.action_history:
                recent = self.action_history[-10:]
                hist = "\n\nPrevious actions:\n" + "\n".join(f"  Step {i+1}: {a}" for i, a in enumerate(recent))

            tool_ctx = ""
            if self._last_tool_result:
                tool_ctx = f"\n\nLast tool_call result:\n{self._last_tool_result}"
                self._last_tool_result = None

            # Build the user message - give explicit hint for first step
            if not self.action_history and "tool_call" not in task.lower() and "click" not in task.lower():
                hint = '\n\nHint: Start by using a tool_call action. Example: {"action":"tool_call","tool":"system_monitor.get_cpu_usage","args":{},"reason":"starting task"}'
            else:
                hint = ""
            msg = f"Task: {task}{hist}{tool_ctx}{hint}\n\nRespond with ONE JSON action:"

            try:
                # Run ollama with a timeout so it never hangs forever
                reply_container = [None]
                error_container = [None]

                def _call_ollama():
                    try:
                        # Build messages - include image only if screenshot succeeded
                        messages = [{"role": "system", "content": system}]
                        if ss is not None:
                            messages.append({"role": "user", "content": msg, "images": [ss]})
                        else:
                            messages.append({"role": "user", "content": msg})

                        resp = ollama.chat(model=model, messages=messages,
                                           options={"temperature": 0.1, "num_predict": 256})
                        # Support both Pydantic object and dict access patterns
                        if hasattr(resp, 'message'):
                            m_obj = resp.message
                            reply_container[0] = m_obj.content if hasattr(m_obj, 'content') else str(m_obj)
                        elif isinstance(resp, dict):
                            reply_container[0] = resp.get("message", {}).get("content", "")
                        else:
                            reply_container[0] = str(resp)
                    except Exception as ex:
                        error_container[0] = str(ex)

                ollama_thread = threading.Thread(target=_call_ollama, daemon=True)
                ollama_thread.start()
                ollama_thread.join(timeout=120)  # 2 minute max

                if ollama_thread.is_alive():
                    self.root.after(0, lambda: self._add_error_msg("Model timed out (120s). Try a simpler task or faster model."))
                    status = "error"; break
                if error_container[0]:
                    err_msg = f"Ollama error: {error_container[0]}"
                    self.root.after(0, lambda m=err_msg: self._add_error_msg(m))
                    # Retry up to max_retries before giving up
                    retries += 1
                    if retries < max_retries:
                        retry_msg = f"Retrying... ({retries}/{max_retries})"
                        self.root.after(0, lambda m=retry_msg: self._add_system_msg(m))
                        time.sleep(2)
                        continue
                    status = "error"; break

                reply = reply_container[0] or ""
                if not reply.strip():
                    self.root.after(0, lambda: self._add_error_msg("Model returned empty response. Retrying..."))
                    retries += 1
                    if retries >= max_retries:
                        status = "error"; break
                    continue
            except Exception as e:
                err_msg = f"Ollama error: {e}"
                self.root.after(0, lambda m=err_msg: self._add_error_msg(m))
                status = "error"; break

            # Reset retry counter on successful response
            retries = 0

            ad = self._parse_action(reply)
            desc = f"{ad.get('action', '?')}: {ad.get('reason', '')}"
            self.action_history.append(desc)

            # Detect stuck loops - if last 3 actions are identical OR all empty thinks, stop
            if len(self.action_history) >= 3:
                last3 = self.action_history[-3:]
                is_stuck = (last3[0] == last3[1] == last3[2])
                is_empty_thinks = all("think:" in a and len(a.strip()) < 10 for a in last3)
                if is_stuck or is_empty_thinks:
                    self.root.after(0, lambda: self._add_error_msg(
                        "Agent is stuck in a loop. Stopping. The model may not understand the task - try simpler wording or a different model."))
                    status = "stuck"; break

            if self.verbose_var.get():
                raw = json.dumps(ad, indent=2)
                self.root.after(0, lambda r=raw: self._add_msg("RAW", r, "#555"))

            if self.confirm_var.get() and ad.get("action") not in ("think", "done"):
                self._waiting_confirm = True
                self.root.after(0, lambda a=ad: self._ask_confirm(a))
                while self._waiting_confirm and self.running: time.sleep(0.1)
                if not self.running: status = "stopped"; break
                if self._confirm_denied:
                    self.root.after(0, lambda: self._add_system_msg("Skipped."))
                    time.sleep(delay); continue

            try:
                if not self._execute_action(ad): break
            except pyautogui.FailSafeException:
                self.root.after(0, lambda: self._add_error_msg("EMERGENCY STOP"))
                status = "emergency_stop"; break
            except Exception as e:
                err_msg = f"Action failed: {e}"
                self.root.after(0, lambda m=err_msg: self._add_error_msg(m))

            time.sleep(delay)

        self.running = False

        # Save to history
        add_history_entry(task, self.action_history, model, status)

        if self.sound_var.get():
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONASTERISK)
            except Exception: pass

        self.root.after(0, lambda: self._set_status("Ready", "#888888"))
        self.root.after(0, lambda: self.run_btn.configure(state="normal"))
        self.root.after(0, lambda: self.stop_btn.configure(state="disabled"))
        self.root.after(0, lambda: self.pause_btn.configure(state="disabled"))
        self.root.after(0, lambda: self._add_system_msg("Agent stopped."))

    def _ask_confirm(self, ad):
        action = ad.get("action", "?")
        reason = ad.get("reason", "")
        cf = ctk.CTkFrame(self.chat_frame, fg_color="#2a2a3a", corner_radius=8)
        cf.pack(fill="x", padx=5, pady=4)
        ctk.CTkLabel(cf, text=f"Allow: {action}?", font=("Segoe UI", 12, "bold")).pack(side="left", padx=8)
        def allow(): self._confirm_denied = False; self._waiting_confirm = False; cf.destroy()
        def deny(): self._confirm_denied = True; self._waiting_confirm = False; cf.destroy()
        ctk.CTkButton(cf, text="Allow", width=60, height=24, fg_color="#22c55e", hover_color="#16a34a", command=allow).pack(side="right", padx=4, pady=4)
        ctk.CTkButton(cf, text="Skip", width=55, height=24, fg_color="#dc2626", hover_color="#b91c1c", command=deny).pack(side="right", padx=4, pady=4)

    def _ask_confirm_tool(self, desc):
        """Security gate confirmation for dangerous toolkit operations."""
        cf = ctk.CTkFrame(self.chat_frame, fg_color="#3a2020", corner_radius=8)
        cf.pack(fill="x", padx=5, pady=4)
        ctk.CTkLabel(cf, text="Security:", font=("Segoe UI", 10, "bold"),
                     text_color="#f87171").pack(side="left", padx=(8, 4))
        ctk.CTkLabel(cf, text=desc[:80], font=("Segoe UI", 11),
                     text_color="#fca5a5", wraplength=450).pack(side="left", padx=(0, 8))
        def allow(): self._confirm_denied = False; self._waiting_confirm = False; cf.destroy()
        def deny(): self._confirm_denied = True; self._waiting_confirm = False; cf.destroy()
        ctk.CTkButton(cf, text="Allow", width=60, height=24, fg_color="#22c55e", hover_color="#16a34a", command=allow).pack(side="right", padx=4, pady=4)
        ctk.CTkButton(cf, text="Deny", width=55, height=24, fg_color="#dc2626", hover_color="#b91c1c", command=deny).pack(side="right", padx=4, pady=4)

    def _start_agent(self):
        task = self.input_box.get("1.0", "end").strip()
        if not task or self.running: return
        model = self.model_var.get()
        if not model or model == "Detecting...":
            self._add_error_msg("No model selected."); return
        if not self.model_loaded:
            self._add_error_msg("Model not activated. Click Activate first."); return

        self.input_box.delete("1.0", "end")
        self._add_user_msg(task)
        self.run_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
        self.pause_btn.configure(state="normal")
        self.paused = False
        self.pause_btn.configure(text="Pause")
        self.thread = threading.Thread(target=self._agent_loop, args=(task,), daemon=True)
        self.thread.start()

    def _stop_agent(self):
        self.running = False
        self.paused = False

    def _toggle_pause(self):
        self.paused = not self.paused
        if self.paused:
            self.pause_btn.configure(text="Resume")
            self._set_status("Paused", "#ca8a04")
        else:
            self.pause_btn.configure(text="Pause")
            self._set_status("Running", "#22c55e")

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = ScreenAgent()
    app.run()
