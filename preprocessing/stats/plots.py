import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import glob

# Collect all .txt files from the specified directory
txt_files = glob.glob("*.txt")

# Initialize a figure with two subplots for PC and EC
fig, (ax_pc, ax_ec) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

# Loop over each file and plot the data on the appropriate subplot
for file in txt_files:
    # Read the data from each file into a pandas DataFrame
    data = pd.read_csv(file, delimiter='\t')  # Adjust delimiter if necessary
    
    # Extract the filename without the path and extension
    label = file.split('/')[-1].replace('.txt', '')
    
    # Check for 'PC' or 'EC' column and plot on the respective subplot
    if 'PC' in data.columns:
        ax_pc.plot(data['d'], data['PC'], label=label)
        ax_pc.scatter(data['d'], data['PC'], s=30)
    if 'EC' in data.columns:
        ax_ec.plot(data['d'], data['EC'], label=label)
        ax_ec.scatter(data['d'], data['EC'], s=30)

# Add labels and legend for PC and EC subplots
ax_pc.set_xlabel('Maximum distance')
ax_pc.set_ylabel('Probability of connectivity (PC)')
ax_pc.legend(title='PC')
ax_ec.set_xlabel('Maximum distance')
ax_ec.set_ylabel('Equivalent connectivity (EC)')
ax_ec.legend(title='EC')

# Show the plot with PC and EC data
plt.tight_layout()
plt.show()

# Now, calculate relative difference and plot it
fig, (ax_rel_pc, ax_rel_ec) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

# Loop again for relative difference calculations
for file in txt_files:
    # Process only enriched files and find the corresponding non-enriched file
    if '_enriched' in file:
        # Load enriched data
        enriched_data = pd.read_csv(file, delimiter='\t')
        
        # Construct the non-enriched filename and check if it exists
        non_enriched_file = file.replace('_enriched', '')
        if non_enriched_file in txt_files:
            # Load non-enriched data
            non_enriched_data = pd.read_csv(non_enriched_file, delimiter='\t')
            
            # Calculate relative difference for PC if both files have 'PC' column
            if 'PC' in enriched_data.columns and 'PC' in non_enriched_data.columns:
                relative_diff_pc = ((enriched_data['PC'] - non_enriched_data['PC']) / non_enriched_data['PC']) * 100
                ax_rel_pc.plot(enriched_data['d'], relative_diff_pc, label=file.replace('.txt', ' (PC)'))
                ax_rel_pc.scatter(enriched_data['d'], relative_diff_pc, s=30)
            
            # Calculate relative difference for EC if both files have 'EC' column
            if 'EC' in enriched_data.columns and 'EC' in non_enriched_data.columns:
                relative_diff_ec = ((enriched_data['EC'] - non_enriched_data['EC']) / non_enriched_data['EC']) * 100
                ax_rel_ec.plot(enriched_data['d'], relative_diff_ec, label=file.replace('.txt', ' (EC)'))
                ax_rel_ec.scatter(enriched_data['d'], relative_diff_ec, s=30)

# Add labels and legends for relative difference plots
ax_rel_pc.set_xlabel('Maximum distance')
ax_rel_pc.set_ylabel('Relative Difference (%) in PC')
ax_rel_pc.legend(title='PC Relative Difference')

ax_rel_ec.set_xlabel('Maximum distance')
ax_rel_ec.set_ylabel('Relative Difference (%) in EC')
ax_rel_ec.legend(title='EC Relative Difference')

# Show relative difference plots
plt.tight_layout()
plt.show()
