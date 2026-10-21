import os
import tkinter as tk
from gui import ExcelCombineGUI


def main():
    root = tk.Tk()
    root.title("ExcelMerger")
    try:
        icon = os.path.join(os.path.dirname(os.path.abspath(__file__)), "excelmerger.ico")
        if os.path.exists(icon):
            root.iconbitmap(icon)
    except Exception:
        pass
    ExcelCombineGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main() 

#pyinstaller --onefile --windowed --icon=excelmerger.ico --name ExcelMerger main.py
