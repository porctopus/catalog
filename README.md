# catalog
This is a sample catalog application for the Udacity FSND course. The application implements Google sign in by building on the exercises in the Google sign in course. Once the user is authenticated, they are able to add, edit and delete new items. There is also a JSON endpoint that shows all available items currently in the database.

## Setup
This project requires Python3 and Postgres.

* Clone this repsitory
* The file client_secret.json is required for Google authentication and will be supplied in a zip file to the reviewer. Copy the file into the working folder
* Install required python packages by running ```pip install -r requirements.txt```
* Insert the base category data into the database by running ```psql -d catalog -f categories.sql```
* On the command line, run the following on the command line in the working directory to start the application
```export FLASK_APP=catalog.py```
* Flask will start up on localhost:5000. Navigate to this URL to view the application

## Application
The main page provides a list of categories, a link to the JSON endpoint for the catalog data and the 10 most recently added items. If the user selects a category, they will see a list of items related to that category. If the user then selects a specific item they will be presented with a description of that item.

If the user logs in via the Google sign in button, they will be presented with additional options. The left nav will now include an "Add Item" link where the user can add additional items to the existing categories. Additionally, Edit and Delete options will now be available when viewing items.
