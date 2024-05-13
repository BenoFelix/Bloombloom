# importing modules
from flask import Flask, render_template, redirect, request, url_for, flash
from flask_sqlalchemy import SQLAlchemy
from pytz import timezone
from flask_bcrypt import Bcrypt
from datetime import datetime
from flask_login import UserMixin, login_user, login_required, logout_user, current_user, LoginManager
import smtplib
import string
import secrets
from sqlalchemy import or_

# Flask app initialization
app = Flask(__name__, template_folder='template')
bcrypt = Bcrypt(app)
app.config['SECRET_KEY'] = "e9f72b93cea98af52710f2c9bcf338f4d6f7b93f5b40117d08e646606a733e1f0c078c6b872e040992bded944ea123a1ac9451e7f58a4593d57ccdcda9edb84a"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///extract.db' # Database linking
db = SQLAlchemy(app) # initializing database
# To handle and manage the logging in of user
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return Users.query.get(int(user_id))

# sending emails automatically whenever needed
def mail(email, content, sub):
    # Email and password was removed.
    MY_EMAIL = ""
    MY_PASSWORD = ""
    with smtplib.SMTP("smtp.gmail.com") as connection:
        connection.starttls() # connect with gmail smtp server
        connection.login(MY_EMAIL, MY_PASSWORD)
        message = f"Subject:{sub}\n\n{content}"
        message = message.encode('utf-8')
        connection.sendmail(
            from_addr=MY_EMAIL,
            to_addrs=email,
            msg=message
        )

# Generating 8 digit password while creating an account
def generate_password(length=8):
    characters = string.ascii_letters + string.digits + string.punctuation
    password = ''.join(secrets.choice(characters) for _ in range(length))
    return password

# Database table for storing transaction
class Transactions(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    type = db.Column(db.String(20), nullable=True)
    amount = db.Column(db.Float, nullable=True)
    date_added = db.Column(db.DateTime, default=datetime.now(timezone('Asia/Kolkata')))

# Database table for storing user datas
class Users(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    email = db.Column(db.String(200), nullable=False, unique=True)
    psw = db.Column(db.String(1000), nullable=False)
    amount = db.Column(db.Float, default=0, nullable=False)
    date_added = db.Column(db.DateTime, default=datetime.now(timezone('Asia/Kolkata')))
    transactions_sent = db.relationship('Transactions', foreign_keys='Transactions.sender_id', backref='sender',
                                        lazy=True)
    transactions_received = db.relationship('Transactions', foreign_keys='Transactions.receiver_id', backref='receiver',
                                            lazy=True)

    def __repr__(self):
        return f'<User {self.email}>'

# Handle login page
@app.route('/', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = Users.query.filter_by(email=email).first() # get user data from database by matching with email 
        if user and bcrypt.check_password_hash(user.psw, password): # check the password with the database
            login_user(user)
            return redirect(url_for('home'))
        else:
            flash('Invalid email or password.', 'error')
    return render_template('login.html')

# Handle signup page
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']
        password = generate_password()

        existing_user = Users.query.filter_by(email=email).first()
        if existing_user: # check whether the account is available
            flash('Email already exists. Please choose a different one.', 'error')
            return redirect(url_for('signup'))
        msg = (f"Congratulation, Your account has been Created Successfully\n"
               f"Your account Password is : {password}\n"
               f"Don't Share the Password with anyone.")
        subject = "Your account has been created successfully!"

        hashed_password = bcrypt.generate_password_hash(password).decode('utf-8') # encrypt the paswword
        new_user = Users(name=name, email=email, psw=hashed_password)
        db.session.add(new_user)
        db.session.commit() # adding to database
        mail(request.form['email'], msg, subject)

        flash('Account created successfully! Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('signup.html')

# Handle home page
@login_required
@app.route('/index')
def home():
    return render_template('index.html')

# Handle deposit page
@login_required
@app.route('/deposit', methods=['GET', 'POST'])
def deposit():
    if request.method == 'POST':
        amount = float(request.form['deposit'])
        if amount <= 0:
            flash('Amount must be greater than zero.', 'error')
        else:
            current_user.amount += amount
            transaction = Transactions(sender_id=current_user.id, receiver_id=current_user.id, type='deposit',
                                       amount=amount)
            db.session.add(transaction)
            db.session.commit()
            flash('Deposit successful!', 'success')
            return redirect(url_for('transaction'))
    return render_template('deposit.html')

# Handle withdraw page
@login_required
@app.route('/withdraw', methods=['GET', 'POST'])
def withdraw():
    if request.method == 'POST':
        amount = float(request.form['withdraw_amount'])
        user = current_user
        password = request.form['psw']
        if user and bcrypt.check_password_hash(user.psw, password):
            if amount <= 0:
                flash('Amount must be greater than zero.', 'error')
            elif amount > current_user.amount:
                flash('Insufficient balance.', 'error')
            else:
                current_user.amount -= amount
                transaction = Transactions(sender_id=current_user.id, receiver_id=current_user.id, type='withdraw',
                                           amount=amount)
                db.session.add(transaction)
                db.session.commit()
                flash('Withdrawal successful!', 'success')
                return redirect(url_for('transaction'))
        else:
            flash('Password you have entered was wrong!!', 'error')
    return render_template('withdraw.html')

# handle transfer page
@login_required
@app.route('/transfer', methods=['GET', 'POST'])
def transfer():
    if request.method == 'POST':
        receiver_email = request.form['email']
        amount = float(request.form['transfer_amount'])
        receiver = Users.query.filter_by(email=receiver_email).first()
        user = current_user
        password = request.form['psw']
        if user and bcrypt.check_password_hash(user.psw, password):
            if not receiver:
                flash('Receiver not found.', 'error')
            elif amount <= 0:
                flash('Amount must be greater than zero.', 'error')
            elif amount > current_user.amount:
                flash('Insufficient balance.', 'error')
            else:
                current_user.amount -= amount
                receiver.amount += amount
                transaction = Transactions(sender_id=current_user.id, receiver_id=receiver.id, type='transfer',
                                           amount=amount)
                db.session.add(transaction)
                db.session.commit()
                flash('Transfer successful!', 'success')
                return redirect(url_for('transaction'))
        else:
            flash('Password you have entered was wrong!!', 'error')
    return render_template('transfer.html')

# handle transaction history page
@login_required
@app.route('/transaction')
def transaction():
    transactions = db.session.query(Transactions).filter(
        or_(Transactions.sender_id == current_user.id, Transactions.receiver_id == current_user.id)
    ).all()
    data = []
    for tran in transactions:
        id = tran.id
        send = tran.sender_id
        receive = tran.receiver_id
        type = tran.type
        amount = tran.amount
        time = tran.date_added
        data.append((id, send, receive, type, amount, time))
    return render_template('transaction.html', data=data)

# Handle logout
@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
    logout_user()
    flash("You Have Been Logged Out!")
    return redirect(url_for('login'))

# handle dashboard page
@app.route('/dashboard', methods=['GET', 'POST'])
@login_required
def dashboard():
    row = [current_user.id, current_user.name, current_user.email, current_user.amount, current_user.date_added]
    return render_template('dashboard.html', data=row)


if __name__ == "__main__":
    with app.app_context():
        db.create_all() # create table in database
    app.run() # run app
