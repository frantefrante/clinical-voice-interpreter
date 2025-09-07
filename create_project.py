#!/usr/bin/env python3
"""Script per creare rapidamente la struttura del progetto"""

import os
from pathlib import Path

def create_project_structure():
    """Crea la struttura del progetto"""
    
    # Cartelle da creare
    folders = [
        "src",
        "output",
        "output/sessions", 
        "output/transcriptions",
        "output/exports",
        "tests",
        "docs"
    ]
    
    # File vuoti da creare
    empty_files = [
        "src/__init__.py",
        "tests/__init__.py"
    ]
    
    # Crea cartelle
    for folder in folders:
        Path(folder).mkdir(parents=True, exist_ok=True)
        print(f"✅ Creata cartella: {folder}")
    
    # Crea file vuoti
    for file_path in empty_files:
        Path(file_path).touch()
        print(f"✅ Creato file: {file_path}")
    
    print("\n📁 Struttura progetto creata!")
    print("Ora copia i contenuti degli artifacts nei rispettivi file.")

if __name__ == "__main__":
    create_project_structure()