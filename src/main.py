import os
import shutil
import argparse
import logging
import utils

# TODO
# 1 - Change the way ISOs are being extracted so it stops needing 7z installed
# 2 - Actually write the ordering function
# 3 - Maybe use a class that gets everything right from the start and then just use the instance's variables
# 4 - Implement reload option so the games/tools list can be refreshed
# 5 - Maybe show game list as a table?
# 6 - Move FOLDERS const to utils

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("app.log"),
        logging.StreamHandler()
    ]
)

FOLDERS = {
  "ISO": "ISO",
  "GAME": "PSP\\GAME"
}

def list_files(input_dir):
    """
    Lists games/tools, sorted by creation/last modified date.
    """
    iso_folder = os.path.join(input_dir, FOLDERS["ISO"])
    psp_game_folder = os.path.join(input_dir, FOLDERS["GAME"])

    try:
        all_items = utils.filter_directory(utils.parse_directory(iso_folder), utils.SearchTypes.ISO)
        all_items.extend(utils.filter_directory(utils.parse_directory(psp_game_folder), utils.SearchTypes.DIR))
        all_items.sort(key=lambda item: item["timestamp"], reverse=True)
    except:
        return logging.error(f"An error occurred while parsing the directories")

    if len(all_items) == 0:
        return logging.warning("No games/tools were found")

    for index, item in enumerate(all_items):
        print(f"{index + 1}. {item["name"]} - {item["date"]}")

def rename_files(input_dir):
    """
    Renames ISO files in the given directory based on their PARAM.SFO titles.
    """
    temp_dir = os.path.join(os.path.abspath(os.getcwd()), "temp")
    os.makedirs(temp_dir, exist_ok=True)
    
    iso_folder = os.path.join(input_dir, FOLDERS["ISO"])
    isos = utils.filter_directory(utils.parse_directory(iso_folder), utils.SearchTypes.ISO)
    
    for iso in isos:
        iso_path = os.path.join(iso[-1], iso[0])
        file_name = iso[0][:-4]
        logging.info(f"Processing: {iso_path}")

        try:
            sfo_path = utils.extract_sfo(iso_path, temp_dir)
            if not sfo_path or not os.path.isfile(sfo_path):
                logging.warning(f"Failed to extract PARAM.SFO from {iso_path}. Skipping.")
                continue
              
            title = utils.parse_sfo(sfo_path, "TITLE")
            if not title:
                logging.warning(f"Failed to get TITLE from {sfo_path}. Skipping.")
                continue
              
            sanitized_title = utils.sanitize_filename(title)
            if not sanitized_title:
                logging.warning(f"Invalid TITLE extracted from {sfo_path}. Skipping.")
                continue

            new_iso_path = os.path.join(iso[-1], sanitized_title + utils.SearchTypes.ISO.value)
            os.rename(iso_path, new_iso_path)
            logging.info(f"Renamed '{file_name}' to '{sanitized_title + utils.SearchTypes.ISO.value}'")
        except Exception as e:
            logging.error(f"An error occurred while processing '{file_name}': {e}")

    shutil.rmtree(temp_dir, ignore_errors=True)
    logging.info("Renaming complete.")

def reorder_files(input_dir):
    """
    Orders files alphabetically.
    """
    try:
        pass
        # TODO
    except Exception as e:
        logging.error(f"An error occurred while reordering files: {e}")

def main():
    """
    Main function to display a menu and handle user input.
    """
    parser = argparse.ArgumentParser(description="Manage your PSP library.")
    parser.add_argument(
        "-i",
        "--input",
        required=True,
        help="Directory containg a known PSP structure.",
    )
    
    args = parser.parse_args()
    input_dir = args.input
    
    if not os.path.isdir(input_dir):
        logging.error(f"Directory '{input_dir}' does not exist.")
        return

    while True:
        print("\n1. List")
        print("2. Rename")
        print("3. Order (A-Z)")
        print("4. Reload drive")
        print("5. Exit")
        choice = input("Enter your choice: ")
        print()
        
        if choice == "1":
            list_files(input_dir)
        elif choice == "2":
            rename_files(input_dir)
        elif choice == "3":
            reorder_files(input_dir)
        elif choice == "4":
            print("Exiting...")
            break
        else:
            print("Invalid choice. Please try again.")
        
if __name__ == "__main__":
    main()