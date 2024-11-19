import pandas as pd

# Load the JSON file
data = pd.read_json(r'C:\Users\admin\Documents\GitHub\JustForTest\test\alarm.json')

# # Print the number of rows and the first few rows
# print(f"Number of rows read: {len(data)}")
# print(data.head())  # Display the first few rows

# Save to Excel file
data.to_excel('test/alarm.xlsx', index=False)
