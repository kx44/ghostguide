---
title: 12. Virtual Environments and Packages — Python 3.15.2 documentation
app: Terminal
author_version: 3.15.2
source:
  type: web
  url: https://docs.python.org/3/tutorial/venv.html
  hash: c135e049d3147cef
start_state: Terminal open with Python installed and working directory ready
compiled:
  model: muse-spark-1.3
  prompts: e729c706c779
---

# Creating virtual environments

## Step 1 — Create virtual environment
```yaml
action: type
target:
  label: Terminal
  kind: window
params:
  then_key: Enter
  value: python -m venv tutorial-env
why: Creates an isolated folder for this project's packages, so they don't clash with other projects.
check: tutorial-env folder is created in the current directory
source:
  anchor: '#12-2-creating-virtual-environments'
confidence: high
```
## Step 2 — Activate environment on Windows
```yaml
action: type
target:
  label: Terminal
  kind: window
params:
  then_key: Enter
  value: tutorial-env\Scripts\activate
why: Switches the terminal to use that isolated folder, so Python and installs apply only to this project.
check: prompt shows (tutorial-env) prefix
source:
  anchor: '#12-2-creating-virtual-environments'
confidence: high
optional: true
```
## Step 3 — Activate environment on Unix or macOS
```yaml
action: type
target:
  label: Terminal
  kind: window
params:
  then_key: Enter
  value: source tutorial-env/bin/activate
why: Switches the terminal to the isolated setup on Mac or Linux, keeping installs separate to this project.
check: prompt shows (tutorial-env) prefix
source:
  anchor: '#12-2-creating-virtual-environments'
confidence: high
```
## Step 4 — Deactivate virtual environment
```yaml
action: type
target:
  label: Terminal
  kind: window
params:
  then_key: Enter
  value: deactivate
why: Leaves the isolated setup and returns to normal Python, so later commands affect the whole computer again.
check: prompt no longer shows (tutorial-env) prefix
source:
  anchor: '#12-2-creating-virtual-environments'
confidence: high
```

# Managing packages with pip

## Step 5 — Install novas package
```yaml
action: type
target:
  label: Terminal
  kind: window
params:
  then_key: Enter
  value: python -m pip install novas
why: Adds the novas package to the active environment, so its code can be imported by this project.
check: terminal reports successful install of novas
source:
  anchor: '#12-3-managing-packages-with-pip'
confidence: high
```
## Step 6 — Install specific requests version
```yaml
action: type
target:
  label: Terminal
  kind: window
params:
  then_key: Enter
  value: python -m pip install requests==2.6.0
why: Installs that exact version of the requests package into the active environment for the project to use.
check: terminal reports successful install of requests 2.6.0
source:
  anchor: '#12-3-managing-packages-with-pip'
confidence: high
```
## Step 7 — Upgrade requests package
```yaml
action: type
target:
  label: Terminal
  kind: window
params:
  then_key: Enter
  value: python -m pip install --upgrade requests
why: Replaces the installed requests with its newest available release for the project to use.
check: terminal reports successful upgrade of requests
source:
  anchor: '#12-3-managing-packages-with-pip'
confidence: high
```
## Step 8 — Show requests package info
```yaml
action: type
target:
  label: Terminal
  kind: window
params:
  then_key: Enter
  value: python -m pip show requests
why: Displays the installed version, location and dependencies, so you can check what is actually in use.
check: terminal shows requests version, location and requirements
source:
  anchor: '#12-3-managing-packages-with-pip'
confidence: high
```
## Step 9 — List installed packages
```yaml
action: type
target:
  label: Terminal
  kind: window
params:
  then_key: Enter
  value: python -m pip list
why: Lists every package in the active environment, so you can see what is installed.
check: terminal lists installed packages
source:
  anchor: '#12-3-managing-packages-with-pip'
confidence: high
```
## Step 10 — Freeze requirements to file
```yaml
action: type
target:
  label: Terminal
  kind: window
params:
  then_key: Enter
  value: python -m pip freeze > requirements.txt
why: Writes the exact installed versions to a file, so the same setup can be recreated later.
check: requirements.txt file appears in working directory
verify:
  file:
    path: requirements.txt
    contains: requests
    exists: true
source:
  anchor: '#12-3-managing-packages-with-pip'
confidence: high
```
## Step 11 — View requirements file
```yaml
action: type
target:
  label: Terminal
  kind: window
params:
  then_key: Enter
  value: cat requirements.txt
why: Shows the saved version list, so you can confirm what will be reinstalled elsewhere.
check: terminal displays contents of requirements.txt
source:
  anchor: '#12-3-managing-packages-with-pip'
confidence: high
```
## Step 12 — Install from requirements file
```yaml
action: type
target:
  label: Terminal
  kind: window
params:
  then_key: Enter
  value: python -m pip install -r requirements.txt
why: Installs all packages listed in that file, so another machine gets the same working setup.
check: terminal reports successful install from requirements.txt
source:
  anchor: '#12-3-managing-packages-with-pip'
confidence: high
```
