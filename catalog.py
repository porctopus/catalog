from flask import Flask, render_template, make_response, redirect, jsonify
from flask_sqlalchemy import SQLAlchemy, request
from flask import session as login_session
import random
import string
import httplib2
import json
import requests
from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError

CLIENT_ID = json.loads(open('client_secret.json', 'r').read())['web']['client_id']

app = Flask(__name__)

app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql:///catalog'
app.config['SECRET_KEY'] = 'secret'

db = SQLAlchemy(app)

# define database tables
class Categories(db.Model):
    category_id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(50))
    items = db.relationship('Items', backref='category', lazy='dynamic')


class Items(db.Model):
    item_id = db.Column(db.Integer, primary_key=True)
    item_name = db.Column(db.String(50))
    item_desc = db.Column(db.String(200))
    category_id = db.Column(db.Integer, db.ForeignKey('categories.category_id'))


@app.route('/gconnect', methods=['POST'])
def gconnect():
    # Validate state token
    if request.args.get('state') != login_session['state']:
        response = make_response(json.dumps('Invalid state parameter.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    # Obtain authorization code
    code = request.data

    try:
        # Upgrade the authorization code into a credentials object
        oauth_flow = flow_from_clientsecrets('client_secret.json', scope='')
        oauth_flow.redirect_uri = 'postmessage'
        credentials = oauth_flow.step2_exchange(code)
    except FlowExchangeError:
        response = make_response(
            json.dumps('Failed to upgrade the authorization code.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Check that the access token is valid.
    access_token = credentials.access_token
    print("Access token: "+ access_token)
    url = ('https://www.googleapis.com/oauth2/v1/tokeninfo?access_token=%s'
           % access_token)
    h = httplib2.Http()
    result = json.loads(h.request(url, 'GET')[1].decode('utf8'))
    print(result)
    # If there was an error in the access token info, abort.
    if result.get('error') is not None:
        response = make_response(json.dumps(result.get('error')), 500)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is used for the intended user.
    gplus_id = credentials.id_token['sub']
    if result['user_id'] != gplus_id:
        response = make_response(
            json.dumps("Token's user ID doesn't match given user ID."), 401)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Verify that the access token is valid for this app.
    if result['issued_to'] != CLIENT_ID:
        response = make_response(
            json.dumps("Token's client ID does not match app's."), 401)
        print("Token's client ID does not match app's.")
        response.headers['Content-Type'] = 'application/json'
        return response

    stored_access_token = login_session.get('access_token')
    if stored_access_token is not None:
        print('Stored Access Token (Login): ' + stored_access_token)
        print('Get from Login_Session (Login): ' +login_session.get('access_token'))
    stored_gplus_id = login_session.get('gplus_id')
    if stored_access_token is not None and gplus_id == stored_gplus_id:
        response = make_response(json.dumps('Current user is already connected.'),
                                 200)
        response.headers['Content-Type'] = 'application/json'
        return response

    # Store the access token in the session for later use.
    print("Credentials token: "+credentials.access_token)
    login_session['access_token'] = credentials.access_token
    login_session['gplus_id'] = gplus_id

    # Get user info
    userinfo_url = "https://www.googleapis.com/oauth2/v1/userinfo"
    params = {'access_token': credentials.access_token, 'alt': 'json'}
    answer = requests.get(userinfo_url, params=params)

    data = answer.json()

    login_session['username'] = data['name']

    response = make_response("You are now logged in as %s" % login_session['username'], 200)

    return response


@app.route('/gdisconnect')
def gdisconnect():
    access_token = login_session.get('access_token')
    if access_token is not None:
        print('Access Token (Disconnect): ' + access_token)
    if access_token is None:
        print('Access Token is None')
        response = make_response(json.dumps('Current user not connected.'), 401)
        response.headers['Content-Type'] = 'application/json'
        return response
    print('In gdisconnect access token is %s' % (access_token))
    print('User name is: ')
    print(login_session['username'])
    url = 'https://accounts.google.com/o/oauth2/revoke?token=%s' % login_session['access_token']
    h = httplib2.Http()
    result = h.request(url, 'GET')[0]
    print('result is ')
    print(result)
    if result['status'] == '200':
        del login_session['access_token']
        del login_session['gplus_id']
        del login_session['username']
        response = make_response('<p>Successfully disconnected.</p>'
                                 '<a href="/">Return to the home page</a>', 200)
        return response
    else:
        response = make_response('<p>Failed to revoke token for given user.<p>', 400)
        return response


@app.route('/')
def catalog_items():
    # get state for login and user status
    get_user_state = setup_state()

    # return all the catalog items and most recently added items

    items = Items.query.order_by(Items.item_id.desc()).limit(5)
    categories = Categories.query.order_by(Categories.category_id).all()

    return render_template('catalog.html', cat=categories, STATE=get_user_state[0],
                           recent_items=items, logged_in=get_user_state[1])


@app.route('/add_item', methods=['GET', 'POST'])
def add_item():
    # check if user is logged in, redirect to home if not
    if 'username' not in login_session:
        return redirect('/')

    # get state for login and user status
    get_user_state = setup_state()

    if request.method == 'GET':
        # retrieve the categories from the database and display them in the add form

        categories = Categories.query.order_by(Categories.category_id).all()
        return render_template('add.html', cat=categories, STATE=get_user_state[0],
                               logged_in=get_user_state[1])

    if request.method == 'POST':

        # handle the add item request

        category = Categories.query.filter(Categories.category == request.form['category']).first()

        new_item = Items(item_name = request.form['itemName'],
                         item_desc = request.form['itemDescription']
                         )

        category.items.append(new_item)

        db.session.add(category)
        db.session.commit()

        alert='Item successfully added!'

        categories = Categories.query.order_by(Categories.category_id).all()

        return render_template('add.html', cat=categories, alert=alert, STATE=get_user_state[0],
                               logged_in=get_user_state[1])


@app.route('/edit_item/<selected_cat>/<selected_item>', methods=['GET', 'POST'])
def edit_item(selected_cat, selected_item):
    # check if user is logged in, redirect to home if not
    if 'username' not in login_session:
        return redirect('/')

    # get state for login and user status
    get_user_state = setup_state()

    if request.method == 'GET':

        # retrieve the data from the database and display in the edit form

        categories = Categories.query.order_by(Categories.category_id).all()
        item = db.session.query(Items) \
            .join(Categories) \
            .filter(Categories.category == selected_cat,
                    Items.item_name == selected_item) \
            .first()

        return render_template('edit.html',
                               cat=categories,
                               item_name=item.item_name,
                               item_cat=item.category.category,
                               item_desc=item.item_desc,
                               STATE=get_user_state[0],
                               logged_in=get_user_state[1])

    if request.method == 'POST':

        # update the edited item in the database

        item = db.session.query(Items)\
            .join(Categories)\
            .filter(Categories.category == selected_cat,
                    Items.item_name == selected_item)\
            .first()

        item.item_name = request.form['itemName']
        item.item_desc = request.form['itemDescription']

        db.session.add(item)
        db.session.commit()

        return redirect("/catalog/"+item.item_name, code=302)


@app.route('/delete_item/<selected_cat>/<selected_item>', methods=['GET', 'POST'])
def delete_item(selected_cat, selected_item):
    # check if user is logged in, redirect to home if not
    if 'username' not in login_session:
        return redirect('/')

    # get state for login and user status
    get_user_state = setup_state()

    if request.method == 'GET':

        # retrieve the data from the database and display in the edit form

        categories = Categories.query.order_by(Categories.category_id).all()
        item = db.session.query(Items) \
            .join(Categories) \
            .filter(Categories.category == selected_cat,
                    Items.item_name == selected_item) \
            .first()

        return render_template('delete.html',
                               cat=categories,
                               item_name=item.item_name,
                               item_cat=item.category.category,
                               item_desc=item.item_desc,
                               STATE=get_user_state[0],
                               logged_in=get_user_state[1])

    if request.method == 'POST':

        # update the edited item in the database

        item = db.session.query(Items)\
            .join(Categories)\
            .filter(Categories.category == selected_cat,
                    Items.item_name == selected_item)\
            .first()

        db.session.delete(item)
        db.session.commit()

        return redirect("/categories/"+selected_cat, code=302)


@app.route('/categories/<selected_cat>')
def display_category(selected_cat):
    # get state for login and user status
    get_user_state = setup_state()

    # display the items from the selected category

    categories = Categories.query.order_by(Categories.category_id).all()
    get_items = Categories.query.filter(Categories.category == selected_cat).first()

    return render_template('items.html', cat=categories, items=get_items.items,
                           STATE=get_user_state[0], logged_in=get_user_state[1])


@app.route('/catalog/<selected_item>')
def display_item(selected_item):
    # get state for login and user status
    get_user_state = setup_state()

    # retrieve and display the selected item description
    categories = Categories.query.order_by(Categories.category_id).all()
    get_item = Items.query.filter(Items.item_name == selected_item).first()

    return render_template('description.html', cat=categories, item_name=get_item.item_name,
                           item_desc=get_item.item_desc, STATE=get_user_state[0], logged_in=get_user_state[1])


@app.route('/JSON')
def display_JSON():
    # retrieve and display all category and item information

    json_data = {}
    categories = Categories.query.order_by(Categories.category_id).all()

    for c in categories:

        if c.items is not None:
            item_list = []
            for i in c.items:

                item={}

                item["item_name"] = i.item_name
                item["item_desc"] = i.item_desc

                item_list.append(item)

        json_data[c.category] = item_list


    return jsonify(json_data)

def setup_state():
    # pass user state to dynamically update content
    logged_in = ''
    if 'username' in login_session:
        logged_in = True

    # handle state for Google login
    state = ''.join(random.choice(string.ascii_uppercase + string.digits)
                    for x in range(32))
    login_session['state'] = state

    return state, logged_in
