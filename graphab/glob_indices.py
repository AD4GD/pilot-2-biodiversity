import os
import sys
import pandas as pd
from collections import defaultdict
import yaml
import argparse
import matplotlib.pyplot as plt

print("Logs are redirected to /logs")
sys.stdout = open('logs/glob_indices.log', 'w') #to log
sys.stderr = sys.stdout

def append_year2txt(output_dir: str) -> None:
    """Appends the year column to each .txt file in the directory.
    
    Parameters:
    output_dir (str): path to the output directory.

    Returns:
    None
    """

    for root, _, files in os.walk(output_dir):
        for file in files:
            if file.startswith("glob") and file.endswith(".txt"):
                file_path = os.path.join(root, file)
                parts = file.replace(".txt", "").split("_")
                if len(parts) < 3:
                    continue  # skip if the filename doesn't match the pattern
                year = parts[2]
                
                df = pd.read_csv(file_path, sep='\t')
                df['year'] = year  # append the year column
                df.to_csv(file_path, sep='\t', index=False)
                print(f"Processed {file_path} with year {year}")

def concat_files(output_dir: str, case_study: str) -> str:
    """Concatenates all .txt files, merging based on common keys.

    Parameters:
    output_dir (str): path to the output directory.
    case_study (str): The name of the case study.

    Returns:
    out_csv (str): a path to the generated glob_csv file.
    """
    unique_fifth_columns = set()
    data_frames = []
    
    for root, _, files in os.walk(output_dir):
        for file in files:
            if file.startswith("glob") and file.endswith(".txt"):
                print(f"Processing: {file}...")
                file_path = os.path.join(root, file)
                df = pd.read_csv(file_path, sep='\t')
                
                # extract the name of metric from filename       
                metric = file.split('_')[1] if '_' in file else "Unknown"
                df['metric'] = metric
                df.metric = [metric] * len(df)  # set the entire metric column to the extracted value

                unique_fifth_columns.update(df.metric)
                print(unique_fifth_columns)
                '''
                if "EC" in index or "PC" in index:
                    unique_fifth_columns.add(df.columns[4])
                if "IIC" in index or "NC" in index:
                    unique_fifth_columns.add(df.columns[1])
                '''
                data_frames.append(df)
    
    print(type(data_frames))

    # DEBUG
    '''
    for i, df in enumerate(data_frames):
        print(f"DataFrame {i}:\n", df.head())  # print the first few rows of each df
    '''
    variations = sorted(unique_fifth_columns)
    print("Variations are:", variations)
    
    merged_data = defaultdict(lambda: {'metric': None})
    
    for df in data_frames:
        '''
        metric = df.metric
        print(col5_name)
        '''
        print(f"Metric: {df.metric}") # DEBUG
        
        # NOTE: DEPRECATED
        ''' 
        # check that the DataFrame has enough columns before accessing them
        if len(df.columns) < 6:
            print(f"Warning: {file_path} does not have enough columns to create key.")
            # continue
        '''
        
        for _, row in df.iterrows():
            try:
                metric_val = row['metric']
                if metric_val in ["EC", "PC"]:
                    key = tuple(row.iloc[[0, 1, 2, 3, 4, 5]])  # using columns 0, 1, 2, 3, 4, 5
                elif metric_val in ["IIC", "NC"]:
                    key = (row.iloc[0], "", "", "", row.iloc[1], row.iloc[2])  # using columns 0, 2, 5
                else:
                    key = None

                print(f"Generated key: {key}, metric: {metric_val}")  # NOTE: debug
                merged_data[key] = {'metric': metric_val} # store value in corresponding column
                '''merged_data[key][metric] = metric_val  ''' # NOTE - old structure
                '''pprint.pprint(merged_data)''' # NOTE: debug
            except IndexError as e:
                print(f"Error processing row: {e}, Row data: {row.to_dict()}")  # NOTE: debug
                continue

    final_data = []
    for key, values in merged_data.items():
        final_data.append(list(key) + [values['metric'], case_study])

    
    columns = list(df.columns[[0, 1, 2, 3, 4, 5]]) + ['metric', 'case_study'] # create df
    columns[4] = 'metric_val' # rename column with the values of metrics
    final_df = pd.DataFrame(final_data, columns=columns)
    final_df['case_study'] = case_study


    os.makedirs(output_dir, exist_ok=True) # create output dir
    
    glob_txt = os.path.join(output_dir, "concat_glob.txt")
    glob_csv = os.path.join(output_dir, "concat_glob.csv")
    final_df.to_csv(glob_txt, sep='\t', index=False)
    final_df.to_csv(glob_csv, sep=',', index=False)
    print("Global indices concatenated and saved.")

    print(f"Output CSV path: {glob_csv}") 
    return glob_csv #return the path to glob_csv path

def combine_glob_csv(glob_csv_paths: list, output_dir: str) -> str:
    """Combine all glob_csv files into one .txt file, adding habitat from the folder name.

    Parameters:
    glob_csv_paths (list): list of paths to glob CSV files.
    output_dir (str): directory to save the combined output.

    Returns:
    output_csv (str): list of paths of glob CSV files (combined by case study)
    """
    combined_data = []
    
    for file_path in glob_csv_paths:
        '''print(f"File path: {file_path}")''' # DEBUG
        habitat = os.path.basename(os.path.dirname(file_path)) # extract name of habitat
        '''print(f"Habitat: {habitat}")''' # DEBUG
        
        df = pd.read_csv(file_path, sep=',')
        df['habitat'] = habitat # add 'habitat' column to df
        combined_data.append(df)
        
    combined_df = pd.concat(combined_data, ignore_index=True) # combine dfs
    
    output_csv = os.path.join(output_dir, "stats_glob.csv")
    combined_df.to_csv(output_csv, sep=',', index=False)
    print(f"Combined data saved to {output_csv}")

    return output_csv

def create_vis(csv: str, case_studies: bool, habitats: bool) -> str:
    ''''Creates plots for the output CSV

    Parameters:
    csv (str): path to the final CSV
    case_studies (bool): specifies if there are multiple case studies defined
    habitats (bool): specifies if there are multiple habitats defined

    Returns:
    plot (str): path to the final visualisation
   '''
    df = pd.read_csv(csv, sep=',')

    # indices = df[]
    # years = df[]

    dfs = dict(tuple(df.groupby('metric')))
    num_metric = len(dfs)
    fig,axs=plt.subplots(num_metric, 1, figsize=(10,5*num_metric), sharex=True)

    if num_metric==1:
        axs=[axs] # make list iterable
    
    for ax, (metric, metric_df) in zip(axs, dfs.items()):
        sorted_df = metric_df.sort_values('year')  # sort for x-axis consistency

        if habitats and 'habitat' in sorted_df.columns:
            for habitat, sub_df in sorted_df.groupby('habitat'):
                ax.plot(
                    sub_df['year'],
                    sub_df['metric_val'],
                    marker='o',
                    label={habitat}
                )
        else:
            ax.plot(
                sorted_df['year'],
                sorted_df['metric_val'],
                marker='o',
                label=metric
            )

        ax.set_title(metric)
        ax.set_ylabel('Value')
        ax.set_xticks(sorted(sorted_df['year'].unique()))
        ax.legend(title='Habitats', loc='center left', bbox_to_anchor=(1.0, 0.5)) # move legend out

    # plt.figure(figsize=(9, 20))
    axs[-1].set_xlabel('Year') # make label for last plot
    plt.xlabel('Year') 
    # plt.plot()
    plt.suptitle('Dynamics of global indices', fontsize=14, fontweight='bold')
    plt.tight_layout(rect=[0, 0, 0.85, 0.97])
    plt.show()

    output_path = os.path.splitext(csv)[0] + '_plot.png'
    plt.savefig(output_path)
    plt.close(fig)

    return output_path

    # TODO - to create plt.subplot for multiple case studies (if True)

def glob_wrapper(case_study: str, del_temp: bool = False) -> None:
    """Calling appending txt files and concatenation based on the case study
    Parameters:
    case_study (str): name of the case study
    del_temp (bool): delete temporary files created by Graphab (each value in separate txt)

    Returns:
    None
    """
    print(f"Running case study: {case_study}")
    glob_csv_paths = [] # init list with paths to global csv outputs

    config_dir = os.path.join("config", case_study)
    config_files = [
      f for f in os.listdir(config_dir)
      if f.endswith(".yaml") and "multi" not in f
    ]

    config_files = [os.path.join(config_dir, f) for f in config_files]
    config_files_str = '\n'.join(config_files)
    print(f"Configuration files are:\n{config_files_str}")
    print("*" * 40)

    mult_habitats = len(config_files) > 1 # flag showing number of habitats considered

    for config in config_files:
        with open(config, "r") as f:
            config = yaml.safe_load(f)
    
        # find the habitat alias
        for key, value in config.items():
            if value == config['habitat']:
                habitat = key.replace('habitat_', '')
                break
        output_dir = os.path.join("data", case_study, "output", habitat)
        output_dir_case_study = os.path.dirname(output_dir)
        output_dir_parent = os.path.join(os.path.dirname(output_dir_case_study), "stats")

        '''print(f"Output directory: {output_dir}")''' # NOTE: DEBUG
        append_year2txt(output_dir)
        glob_csv_path = concat_files(output_dir, case_study)

        glob_csv_paths.append(glob_csv_path) # upd list with glob csv outputs
   
    print(f"Output directory for combined stats: {output_dir_case_study}")
    glob_csv_case_study = combine_glob_csv(glob_csv_paths, output_dir_case_study)
    print(glob_csv_case_study)

    plot=create_vis(glob_csv_case_study, case_studies=False, habitats=mult_habitats)
    # TODO - to add grouping by case studies and habitats
    if plot:
        print(f"Plot successfully created and saved to: {plot}")
    else:
        print("Plot creation failed.")
    print("*" * 40)

    if del_temp: # delete temporary txt files for each year and case study
        current_dir = os.getcwd()
        print(f"Deleting temporary files in {current_dir}...")
        for root, _, files in os.walk(current_dir):
            for file in files:
                if file.startswith("glob") and file.endswith(".txt"):
                    file_path = os.path.join(root, file)
                    print(f"Deleting file: {file_path}")
    # TODO - delete more files
    print("*" * 40)
    print("*" * 40)

    '''print(f"Output CSVs by case studies: {glob_csv_case_study}")'''
    return glob_csv_case_study

if __name__ == "__main__":
    # set up argparse to handle arguments
    parser = argparse.ArgumentParser(description="Concatenate global indices by case study")
    parser.add_argument(
        "case_studies",  # positional arg
        type=lambda s: s.split(","),  # split input by commas
        help="Comma-separated list of case studies (eg. 'case1,case2,case3')"
    )
    
    parser.add_argument(
        "--combine_case_studies", 
        action='store_true', # True by default
        help="Combine all case studies into one CSV (if specified, True)"
    )

    # parsing the argument
    args = parser.parse_args()

    # calling the wrapper function with the case study argument 
    all_case_study_csvs = []
    for case_study in args.case_studies:
        case_study_csvs = glob_wrapper(case_study=case_study, del_temp=False)
        '''all_case_study_csvs.extend(case_study_csvs)'''
