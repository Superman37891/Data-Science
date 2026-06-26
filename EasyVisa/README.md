Instructions:
* Either 1: Put the EasyVisa.csv (dataset) file in the same working directory as the notebook
* Or 2: Upload the EasyVisa.csv file to Google Drive and replace the path_to_folder variable in the notebook with the path in your local Google Drive to the dataset

Dataset description and problem statement in the notebook as text

You can also potentially speed up the running of this notebook by using a GPU for your runtime

This project extensively used Ensemble Methods on both the original data and undersampled or oversampled data to account for class imbalance. Data was oversampled using either sklearn's resample function, SMOTE, or tomek links
