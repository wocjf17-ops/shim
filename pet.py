name: Build Pet EXE

on: [push, workflow_dispatch]

jobs:
  build:
    runs-on: windows-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install pillow pyinstaller

      - name: Prepare Image and Build
        shell: cmd
        run: |
          dir
          if exist "PET.PNG" copy /Y "PET.PNG" "pet.png"
          if exist "pet_2.png" copy /Y "pet_2.png" "pet.png"
          if exist "PET_2.PNG" copy /Y "PET_2.PNG" "pet.png"
          pyinstaller --onefile --noconsole --add-data "pet.png;." pet.py

      - name: Upload EXE Artifact
        uses: actions/upload-artifact@v4
        with:
          name: desktop-pet-exe
          path: dist/pet.exe
