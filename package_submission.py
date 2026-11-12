import os
import shutil
import zipfile

def package_submission(group_name="Group_Assignment4"):
    base_dir = os.path.abspath(os.path.dirname(__file__))
    target_root = os.path.join(base_dir, "submission_package", group_name)
    
    if os.path.exists(target_root):
        shutil.rmtree(target_root)
    os.makedirs(target_root, exist_ok=True)
    
    code_files_dir = os.path.join(target_root, "Code_Files")
    eval_data_dir = os.path.join(target_root, "Evaluation_Data")
    os.makedirs(code_files_dir, exist_ok=True)
    os.makedirs(eval_data_dir, exist_ok=True)

    # 1. Copy Code_Files
    # Directories to copy into Code_Files
    dirs_to_copy = ["app", "config", "static", "tests", "vosk_model"]
    for d in dirs_to_copy:
        src = os.path.join(base_dir, d)
        if os.path.exists(src):
            shutil.copytree(src, os.path.join(code_files_dir, d), ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
            print(f"Copied directory {d} to Code_Files/{d}")

    # Files to copy into Code_Files
    files_to_copy = [
        "main.py", "pyproject.toml", "README.md", "REPORT.md",
        "create_presentation_deck.py", "Presentation_Slides.pptx",
        "Demo_Video_Walkthrough_Guide.md", ".env.example"
    ]
    for f in files_to_copy:
        src = os.path.join(base_dir, f)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(code_files_dir, f))
            print(f"Copied file {f} to Code_Files/{f}")

    # 2. Copy Report.pdf
    report_src = os.path.join(base_dir, "Report.pdf")
    if os.path.exists(report_src):
        shutil.copy2(report_src, os.path.join(target_root, "Report.pdf"))
        print(f"Copied Report.pdf to {group_name}/Report.pdf")

    # 3. Copy Demo_Video.mp4
    demo_src = os.path.join(base_dir, "Demo_Video.mp4")
    if os.path.exists(demo_src):
        shutil.copy2(demo_src, os.path.join(target_root, "Demo_Video.mp4"))
        print(f"Copied Demo_Video.mp4 to {group_name}/Demo_Video.mp4")

    # 4. Copy Evaluation_Data
    eval_src_dir = os.path.join(base_dir, "Evaluation_Data")
    for f in os.listdir(eval_src_dir):
        src = os.path.join(eval_src_dir, f)
        if os.path.isfile(src):
            shutil.copy2(src, os.path.join(eval_data_dir, f))
            print(f"Copied Evaluation_Data/{f} to {group_name}/Evaluation_Data/{f}")

    # 5. Create .zip archive
    zip_path = os.path.join(base_dir, "submission_package", f"{group_name}.zip")
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(target_root):
            for file in files:
                abs_file = os.path.join(root, file)
                rel_path = os.path.relpath(abs_file, os.path.join(base_dir, "submission_package"))
                zipf.write(abs_file, rel_path)
    print(f"\nSuccessfully created submission archive: {zip_path}")
    print(f"Archive size: {os.path.getsize(zip_path)} bytes")

if __name__ == "__main__":
    package_submission()
