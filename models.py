from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from sqlalchemy import text
import pytz
IST = pytz.timezone('Asia/Kolkata')

db = SQLAlchemy()

class Admin(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password = db.Column(db.String(100), nullable=False)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)  
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    address = db.Column(db.String(200), nullable=False)
    pincode = db.Column(db.String(10), nullable=False)


class ParkingLot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    price = db.Column(db.Float, nullable=False)
    address = db.Column(db.String(255), nullable=False)
    pincode = db.Column(db.String(10), nullable=False)
    max_spots = db.Column(db.Integer, nullable=False)
    spots = db.relationship('ParkingSpot', backref='lot', lazy=True)


class ParkingSpot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lot.id'), nullable=False)
    spot_number = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(1), nullable=False, default='A')  # 'A': Available, 'O': Occupied

class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spot.id'), nullable=False)
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    cost = db.Column(db.Float)

    spot = db.relationship('ParkingSpot', backref='reservations')


def get_all_lots():
    return ParkingLot.query.all()

def get_available_spots(lot_id):
    return ParkingSpot.query.filter_by(lot_id=lot_id, status='A').all()

def book_spot(spot_id, user_id):
   
    spot = ParkingSpot.query.get(spot_id)
    if not spot or spot.status != 'A':
        return False
    spot.status = 'O'

    start_time_ist = IST.localize(datetime.now())
    reservation = Reservation(spot_id=spot_id, user_id=user_id, start_time=start_time_ist)

    db.session.add(reservation)
    db.session.commit()
    return True



def get_user_reservations(user_id):
    result = db.session.execute(text("""
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
    """), {'uid': user_id})
    reservations = []
    for row in result.fetchall():
        reservations.append({
            'reservation_id': row.reservation_id,
            'start_time': datetime.fromisoformat(row.start_time) if isinstance(row.start_time, str) else row.start_time,
            'end_time': datetime.fromisoformat(row.end_time) if row.end_time and isinstance(row.end_time, str) else row.end_time,
            'cost': row.cost,
            'spot_number': row.spot_number,
            'lot_name': row.lot_name
        })
    return reservations


