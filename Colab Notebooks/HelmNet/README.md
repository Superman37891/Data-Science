DISCLAIMER: I could not get the images.npy file into the GitHub repository due to it well exceeding GitHub's 100 MB file limit

This project focused on using Convolutional Neural Networks (CNNs) to classify whether or not a subject was wearing a helmet in an image (binary classification)

A CNN I trained from scratch achieved an over 90% accuracy on validation set

I then trained 3 more CNNs using transfer learning with Google's VGG-16 model as a base and classification layers on top. One of them used only classification layers on top, one of them added a dropout layer, and one of them added data augmentation and a dropout layer. Each of these achieved an over 96% accuracy on the validation dataset, with my chosen model (the last one) achieving an approximately 97.5% accuracy on the validation set and 96.6% accuracy on the test set

I also added various user-defined functions to streamline repetitive tasks, including one that fully trained the model and chose the weights that led to minimal validation loss, removing the need for me to guess a number of training epochs that worked best for the model. 