import pandas as pd
import os
from typing import Iterable, List, Optional


def read_table_files(
    folder_path: str,
    extensions: Optional[Iterable[str]] = None,
) -> List[pd.DataFrame]:
    """
    Зчитує CSV/Excel файли з вказаної папки та підпапок.

    :param folder_path: шлях до кореневої папки
    :param extensions: розширення файлів, які потрібно шукати
    :return: список DataFrame'ів з доданою колонкою 'File name'
    """
    if extensions is None:
        extensions = (".csv", ".xlsx", ".xls", ".xlsm")

    extensions = tuple(ext.lower() for ext in extensions)
    all_dataframes: List[pd.DataFrame] = []

    for root, dirs, files in os.walk(folder_path):
        for file in files:
            lower_name = file.lower()
            if not lower_name.endswith(extensions):
                continue

            file_path = os.path.join(root, file)
            try:
                if lower_name.endswith(".csv"):
                    df = pd.read_csv(file_path)
                else:
                    df = pd.read_excel(file_path)

                if df.empty:
                    continue

                df.insert(0, "File name", file)
                all_dataframes.append(df)
            except Exception as e:
                print(f"Could not read {file_path}: {e}")

    return all_dataframes


def merge_dataframes(dataframes: Iterable[pd.DataFrame]) -> Optional[pd.DataFrame]:
    dataframes = list(dataframes)
    if dataframes:
        return pd.concat(dataframes, ignore_index=True)
    return None


def save_to_excel(dataframe: Optional[pd.DataFrame], output_file: str) -> None:
    if dataframe is not None:
        dataframe.to_excel(output_file, index=False)
        print(f"Merged file saved as: {output_file}")
    else:
        print("No dataframes to save.")


if __name__ == "__main__":
    # Простий CLI-приклад використання, виконується тільки при прямому запуску файлу
    example_folder = input("Введіть шлях до папки з файлами (або залиште порожнім для виходу): ").strip()
    if example_folder:
        output_file = os.path.join(example_folder, "merged_output.xlsx")
        dfs = read_table_files(example_folder)
        merged_df = merge_dataframes(dfs)
        save_to_excel(merged_df, output_file)
