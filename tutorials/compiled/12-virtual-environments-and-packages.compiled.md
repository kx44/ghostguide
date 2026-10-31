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
  prompts: aea7adb90a1d
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
check: terminal reports successful install from requirements.txt
source:
  anchor: '#12-3-managing-packages-with-pip'
confidence: high
```
