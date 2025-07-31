from flask import Flask, render_template, request, redirect, session, url_for
from models import db, Admin, ParkingLot, ParkingSpot, Reservation, get_all_lots, get_available_spots, book_spot, get_user_reservations
from sqlalchemy import text
from datetime import datetime
import pytz

IST = pytz.timezone('Asia/Kolkata')
app = Flask(__name__)
app.secret_key = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///parking.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db.init_app(app)


#  Home 
@app.route('/')
def home():
    return redirect('/login')

# Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        admin = Admin.query.filter_by(username=username, password=password).first()
        if admin:
            session['user_type'] = 'admin'
            session['user'] = {'id': admin.id, 'username': admin.username}
            return redirect('/admin/dashboard')

        user = db.session.execute(text("SELECT * FROM User WHERE email = :email AND password = :password"),
                                  {'email': username, 'password': password}).fetchone()
        if user:
            session['user_type'] = 'user'
            session['user'] = {'id': user.id, 'name': user.name}
            return redirect('/user/dashboard')

        return render_template('login.html', error="Invalid credentials")

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        name = request.form['name']
        address = request.form['address']
        pincode = request.form['pincode']

        user = db.session.execute(text("SELECT * FROM User WHERE email = :email"), {'email': email}).fetchone()
        if user:
            return render_template('register.html', error="Email already registered.")

        db.session.execute(text("""
            INSERT INTO User (email, password, name, address, pincode)
            VALUES (:e, :p, :n, :a, :pin)
        """), {'e': email, 'p': password, 'n': name, 'a': address, 'pin': pincode})

        db.session.commit()
        return redirect('/login')

    return render_template('register.html')


@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')


#  Admin 
@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('user_type') == 'admin':
        return render_template('admin_dashboard.html', user=session['user'])
    return redirect('/login')


@app.route('/admin/create-lot', methods=['GET', 'POST'])
def create_lot():
    if session.get('user_type') != 'admin':
        return redirect('/login')

    if request.method == 'POST':
        name = request.form['lot_name']           # From <input name="lot_name">
        location = request.form['location']       # From <input name="location">
        address = request.form['address']         # From <input name="address">
        price = float(request.form['price_per_hour'])
        pincode = request.form['pincode']
        max_spots = int(request.form['max_spots'])

        lot = ParkingLot(
            name=name,
            location=location,
            price=price,
            address=address,
            pincode=pincode,
            max_spots=max_spots
        )
        db.session.add(lot)
        db.session.commit()

        for i in range(max_spots):
            spot = ParkingSpot(lot_id=lot.id, spot_number=f"S{i+1}", status='A')
            db.session.add(spot)

        db.session.commit()
        return redirect('/admin/view-lots')

    return render_template('create_lot.html')



@app.route('/admin/view-lots')
def view_lots_admin():
    if session.get('user_type') != 'admin':
        return redirect('/login')

    lots = ParkingLot.query.all()
    lot_details = []
    for lot in lots:
        available = ParkingSpot.query.filter_by(lot_id=lot.id, status='A').count()
        occupied = ParkingSpot.query.filter_by(lot_id=lot.id, status='O').count()
        lot_details.append((lot, available, occupied))

    return render_template('view_lots.html', lots=lot_details)


@app.route('/admin/delete-lot/<int:lot_id>')
def delete_lot(lot_id):
    if session.get('user_type') != 'admin':
        return redirect('/login')

    occupied = ParkingSpot.query.filter_by(lot_id=lot_id, status='O').count()
    if occupied > 0:
        return "Cannot delete lot with occupied spots"

    ParkingSpot.query.filter_by(lot_id=lot_id).delete()
    ParkingLot.query.filter_by(id=lot_id).delete()
    db.session.commit()
    return redirect('/admin/view-lots')

def parse_datetime(value):
    """Convert ISO string to datetime object"""
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return value
@app.route('/admin/view-users')
def view_users():
    if session.get('user_type') != 'admin':
        return redirect('/login')

    users = db.session.execute(text("SELECT * FROM User")).fetchall()
    all_user_data = []

    for user in users:
        reservations_raw = db.session.execute(text("""
            SELECT
                r.id AS reservation_id,
                r.start_time,
                r.end_time,
                r.cost,
                p.spot_number,
                l.name AS lot_name
            FROM reservation r
            JOIN parking_spot p ON r.spot_id = p.id
            JOIN parking_lot l ON p.lot_id = l.id
            WHERE r.user_id = :uid
            ORDER BY r.start_time DESC
        """), {'uid': user.id}).fetchall()

        # Parse each reservation row safely
        reservations = []
        for r in reservations_raw:
            reservations.append({
                'reservation_id': r.reservation_id,
                'start_time': parse_datetime(r.start_time),
                'end_time': parse_datetime(r.end_time),
                'cost': r.cost,
                'spot_number': r.spot_number,
                'lot_name': r.lot_name
            })

        all_user_data.append({
            'id': user.id,
            'name': user.name,
            'email': user.email,
            'address': user.address,
            'pincode': user.pincode,
            'reservations': reservations
        })

    return render_template('view_users.html', users=all_user_data)


# User 
@app.route('/user/dashboard')
def user_dashboard():
    if session.get('user_type') == 'user':
        lots = ParkingLot.query.all()
        return render_template('user_dashboard.html', user=session['user'], lots=lots)
    return redirect('/login')


@app.route('/user/lots')
def user_view_lots():
    if session.get('user_type') != 'user':
        return redirect('/login')

    lots = ParkingLot.query.all()
    lot_availability = [(lot, len(get_available_spots(lot.id))) for lot in lots]
    return render_template('user_view_lots.html', lots=lot_availability)



@app.route('/user/spots/<int:lot_id>')
def user_view_spots(lot_id):
    if session.get('user_type') != 'user':
        return redirect('/login')

    spots = get_available_spots(lot_id)
    lot = ParkingLot.query.get_or_404(lot_id)
    return render_template('user_view_spots.html', spots=spots, lot=lot, lot_id=lot_id)



@app.route('/user/reserve/<int:spot_id>', methods=['POST'])
def reserve_spot_route(spot_id):
    if session.get('user_type') != 'user':
        return redirect('/login')

    user_id = session['user']['id']
    if book_spot(spot_id, user_id):
        return redirect('/user/reservations')
    return "Error: Spot could not be reserved"


@app.route('/user/reservations')
def user_reservations():
    if session.get('user_type') != 'user':
        return redirect('/login')

    user_id = session['user']['id']
    reservations = get_user_reservations(user_id)
    return render_template('user_reservations.html', reservations=reservations)


@app.route('/user/cancel/<int:reservation_id>', methods=['POST'])
def user_cancel_reservation(reservation_id):
    return "Cancel functionality to be implemented"


from datetime import datetime
import pytz

@app.route('/user/complete/<int:reservation_id>', methods=['POST'])
def complete_reservation(reservation_id):
    res = Reservation.query.get_or_404(reservation_id)
    if res.end_time:
        return "Reservation already completed."

    
    IST = pytz.timezone('Asia/Kolkata')
    now_ist = IST.localize(datetime.now())

    if res.start_time.tzinfo is None:
        res.start_time = IST.localize(res.start_time)


    res.end_time = now_ist

    duration = (res.end_time - res.start_time).total_seconds() / 3600

  
    res.cost = round(duration * res.spot.lot.price, 2)

  
    res.spot.status = 'A'

    db.session.commit()
    return redirect('/user/reservations')


if __name__ == '__main__':
    from models import Admin

    with app.app_context():
        db.create_all()

        if not Admin.query.first():
            new_admin = Admin(username='admin@gmail.com', password='@dmin1')
            db.session.add(new_admin)
            db.session.commit()
    app.run(debug=True)

