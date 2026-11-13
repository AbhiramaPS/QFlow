import os
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, abort, flash, jsonify, redirect, render_template, request, session, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import update
from werkzeug.security import check_password_hash, generate_password_hash

app = Flask(__name__, instance_relative_config=True)
os.makedirs(app.instance_path, exist_ok=True)
app.config.update(
    SECRET_KEY=os.getenv('SECRET_KEY', 'local-development-key-change-me'),
    SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL') or 'sqlite:///' + os.path.join(app.instance_path, 'qflow.db'),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
)
db = SQLAlchemy(app)
CSRFProtect(app)


def local_now():
    # This single-campus MVP stores appointment times as local wall-clock times.
    return datetime.now().replace(second=0, microsecond=0)


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(160), unique=True, nullable=False, index=True)
    password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(12), nullable=False, default='customer')
    offerings = db.relationship('Offering', back_populates='provider', cascade='all, delete-orphan')
    reservations = db.relationship('Reservation', back_populates='customer', foreign_keys='Reservation.customer_id')


class Offering(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    description = db.Column(db.String(800), nullable=False, default='')
    duration_minutes = db.Column(db.Integer, nullable=False, default=30)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=local_now)
    provider = db.relationship('User', back_populates='offerings')
    slots = db.relationship('AvailabilitySlot', back_populates='offering', cascade='all, delete-orphan')


class AvailabilitySlot(db.Model):
    __tablename__ = 'availability_slot'
    id = db.Column(db.Integer, primary_key=True)
    offering_id = db.Column(db.Integer, db.ForeignKey('offering.id'), nullable=False, index=True)
    starts_at = db.Column(db.DateTime, nullable=False, index=True)
    ends_at = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(16), nullable=False, default='AVAILABLE', index=True)
    offering = db.relationship('Offering', back_populates='slots')
    reservations = db.relationship('Reservation', back_populates='slot')


class Reservation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False, index=True)
    slot_id = db.Column(db.Integer, db.ForeignKey('availability_slot.id'), nullable=False, index=True)
    status = db.Column(db.String(16), nullable=False, default='PENDING', index=True)
    note = db.Column(db.String(500), nullable=False, default='')
    created_at = db.Column(db.DateTime, nullable=False, default=local_now)
    updated_at = db.Column(db.DateTime, nullable=False, default=local_now, onupdate=local_now)
    customer = db.relationship('User', back_populates='reservations', foreign_keys=[customer_id])
    slot = db.relationship('AvailabilitySlot', back_populates='reservations')


ACTIVE_RESERVATIONS = ('PENDING', 'CONFIRMED')
PROVIDER_ROLES = ('provider', 'admin')  # `admin` keeps accounts from the first QFlow version usable.
CUSTOMER_ROLES = ('customer', 'user')  # `user` keeps existing customer accounts usable.


def current_user():
    user_id = session.get('uid')
    return db.session.get(User, user_id) if user_id else None


def login_required(f):
    @wraps(f)
    def wrapped(*args, **kwargs):
        if not current_user():
            flash('Please sign in to continue.', 'error')
            return redirect(url_for('portal'))
        return f(*args, **kwargs)
    return wrapped


def role_required(*roles):
    def decorate(f):
        @wraps(f)
        @login_required
        def wrapped(*args, **kwargs):
            if current_user().role not in roles:
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorate


def active_reservation_overlap(provider_id, starts_at, ends_at):
    return (db.session.query(AvailabilitySlot.id)
            .join(Offering).join(Reservation)
            .filter(Offering.provider_id == provider_id,
                    Reservation.status.in_(ACTIVE_RESERVATIONS),
                    AvailabilitySlot.starts_at < ends_at,
                    AvailabilitySlot.ends_at > starts_at).first() is not None)


@app.context_processor
def inject_shell_data():
    return {'current_user': current_user()}


@app.route('/')
def home():
    offerings = (Offering.query.join(User, Offering.provider_id == User.id)
                 .filter(Offering.active.is_(True)).order_by(Offering.created_at.desc()).all())
    now = local_now()
    cards = []
    for offering in offerings:
        count = (AvailabilitySlot.query.filter_by(offering_id=offering.id, status='AVAILABLE')
                 .filter(AvailabilitySlot.starts_at > now).count())
        cards.append({'offering': offering, 'available_count': count})
    return render_template('home.html', cards=cards)


@app.route('/login')
@app.route('/register')
def portal():
    return render_template('portal.html')


@app.route('/register/<account_type>', methods=['GET', 'POST'])
def register(account_type):
    role = {'provider': 'provider', 'customer': 'customer'}.get(account_type)
    if not role:
        abort(404)
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        if not name or len(name) > 100 or '@' not in email or len(password) < 8:
            flash('Add your name, a valid email, and a password with at least 8 characters.', 'error')
        elif User.query.filter_by(email=email).first():
            flash('There is already an account with that email. Try signing in instead.', 'error')
        else:
            user = User(name=name, email=email, password=generate_password_hash(password), role=role)
            db.session.add(user)
            db.session.commit()
            session.clear()
            session['uid'] = user.id
            flash('Your account is ready.', 'success')
            return redirect(url_for('provider_dashboard' if role == 'provider' else 'customer_dashboard'))
    return render_template('auth.html', account_type=account_type, registering=True)


@app.route('/login/<account_type>', methods=['GET', 'POST'])
def login(account_type):
    valid_roles = {'provider': PROVIDER_ROLES, 'customer': CUSTOMER_ROLES}
    if account_type not in valid_roles:
        abort(404)
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email', '').strip().lower()).first()
        password = request.form.get('password', '')
        if user and user.role in valid_roles[account_type] and check_password_hash(user.password, password):
            session.clear()
            session['uid'] = user.id
            target = 'provider_dashboard' if account_type == 'provider' else 'customer_dashboard'
            return redirect(url_for(target))
        flash('Those details did not match a ' + account_type + ' account.', 'error')
    return render_template('auth.html', account_type=account_type, registering=False)


@app.route('/logout', methods=['POST'])
@login_required
def logout():
    session.clear()
    return redirect(url_for('home'))


@app.route('/provider')
@role_required(*PROVIDER_ROLES)
def provider_dashboard():
    provider = current_user()
    offerings = Offering.query.filter_by(provider_id=provider.id).order_by(Offering.created_at.desc()).all()
    reservations = (Reservation.query.join(AvailabilitySlot).join(Offering)
                    .filter(Offering.provider_id == provider.id)
                    .order_by(AvailabilitySlot.starts_at.asc()).all())
    return render_template('provider_dashboard.html', offerings=offerings,
                           reservations=reservations, now=local_now())


@app.route('/provider/offering', methods=['POST'])
@role_required(*PROVIDER_ROLES)
def create_offering():
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    duration = request.form.get('duration_minutes', type=int)
    if not name or len(name) > 120 or len(description) > 800 or not duration or not 5 <= duration <= 480:
        flash('Enter a service name, a short description, and a duration from 5 to 480 minutes.', 'error')
    else:
        db.session.add(Offering(provider_id=current_user().id, name=name,
                                description=description, duration_minutes=duration))
        db.session.commit()
        flash('Service added. Add a few times when customers can book it.', 'success')
    return redirect(url_for('provider_dashboard'))


@app.route('/provider/offering/<int:offering_id>/slot', methods=['POST'])
@role_required(*PROVIDER_ROLES)
def create_slot(offering_id):
    offering = db.get_or_404(Offering, offering_id)
    if offering.provider_id != current_user().id:
        abort(403)
    try:
        starts_at = datetime.strptime(request.form.get('starts_at', ''), '%Y-%m-%dT%H:%M')
    except ValueError:
        flash('Choose a valid date and start time.', 'error')
        return redirect(url_for('provider_dashboard'))
    ends_at = starts_at + timedelta(minutes=offering.duration_minutes)
    overlap = (AvailabilitySlot.query.join(Offering)
               .filter(Offering.provider_id == current_user().id,
                       AvailabilitySlot.starts_at < ends_at,
                       AvailabilitySlot.ends_at > starts_at).first())
    if starts_at <= local_now():
        flash('Availability must start in the future.', 'error')
    elif overlap:
        flash('That time overlaps another slot you already listed.', 'error')
    else:
        db.session.add(AvailabilitySlot(offering_id=offering.id, starts_at=starts_at, ends_at=ends_at))
        db.session.commit()
        flash('The time is now open for reservations.', 'success')
    return redirect(url_for('provider_dashboard'))


@app.route('/provider/offering/<int:offering_id>/toggle', methods=['POST'])
@role_required(*PROVIDER_ROLES)
def toggle_offering(offering_id):
    offering = db.get_or_404(Offering, offering_id)
    if offering.provider_id != current_user().id:
        abort(403)
    offering.active = not offering.active
    db.session.commit()
    return redirect(url_for('provider_dashboard'))


@app.route('/provider/reservation/<int:reservation_id>/<action>', methods=['POST'])
@role_required(*PROVIDER_ROLES)
def provider_reservation_action(reservation_id, action):
    reservation = db.get_or_404(Reservation, reservation_id)
    if reservation.slot.offering.provider_id != current_user().id:
        abort(403)
    transitions = {'confirm': ('PENDING', 'CONFIRMED'), 'decline': ('PENDING', 'DECLINED'),
                   'complete': ('CONFIRMED', 'COMPLETED'), 'cancel': ('CONFIRMED', 'CANCELLED')}
    if action not in transitions:
        abort(400)
    old, new = transitions[action]
    if reservation.status == old:
        reservation.status = new
        if new in ('DECLINED', 'CANCELLED') and reservation.slot.starts_at > local_now():
            reservation.slot.status = 'AVAILABLE'
        db.session.commit()
        flash('Reservation updated.', 'success')
    return redirect(url_for('provider_dashboard'))


@app.route('/customer')
@role_required(*CUSTOMER_ROLES)
def customer_dashboard():
    reservations = (Reservation.query.filter_by(customer_id=current_user().id)
                    .join(AvailabilitySlot).order_by(AvailabilitySlot.starts_at.desc()).all())
    return render_template('customer_dashboard.html', reservations=reservations, now=local_now())


@app.route('/offering/<int:offering_id>')
def offering_detail(offering_id):
    offering = db.get_or_404(Offering, offering_id)
    if not offering.active:
        abort(404)
    slots = (AvailabilitySlot.query.filter_by(offering_id=offering.id, status='AVAILABLE')
             .filter(AvailabilitySlot.starts_at > local_now()).order_by(AvailabilitySlot.starts_at).all())
    return render_template('offering.html', offering=offering, slots=slots)


@app.route('/reservation/<int:slot_id>', methods=['POST'])
@role_required(*CUSTOMER_ROLES)
def book_slot(slot_id):
    slot = db.get_or_404(AvailabilitySlot, slot_id)
    if not slot.offering.active or slot.status != 'AVAILABLE' or slot.starts_at <= local_now():
        flash('That time is no longer available. Please choose another.', 'error')
        return redirect(url_for('offering_detail', offering_id=slot.offering_id))
    if active_reservation_overlap(slot.offering.provider_id, slot.starts_at, slot.ends_at):
        flash('The provider has another booking at that time. Please choose another slot.', 'error')
        return redirect(url_for('offering_detail', offering_id=slot.offering_id))
    # Claim the slot with a conditional update so overlapping requests cannot both win.
    claimed = db.session.execute(update(AvailabilitySlot).where(
        AvailabilitySlot.id == slot.id, AvailabilitySlot.status == 'AVAILABLE'
    ).values(status='BOOKED'))
    if claimed.rowcount != 1:
        db.session.rollback()
        flash('Someone just reserved that time. Please choose another.', 'error')
        return redirect(url_for('offering_detail', offering_id=slot.offering_id))
    note = request.form.get('note', '').strip()[:500]
    db.session.add(Reservation(customer_id=current_user().id, slot_id=slot.id, note=note))
    db.session.commit()
    flash('Request sent. The provider will confirm your reservation.', 'success')
    return redirect(url_for('customer_dashboard'))


@app.route('/reservation/<int:reservation_id>/cancel', methods=['POST'])
@role_required(*CUSTOMER_ROLES)
def cancel_reservation(reservation_id):
    reservation = db.get_or_404(Reservation, reservation_id)
    if reservation.customer_id != current_user().id:
        abort(403)
    if reservation.status in ACTIVE_RESERVATIONS:
        if reservation.slot.starts_at <= local_now():
            flash('This appointment has already started, so it can no longer be cancelled here.', 'error')
        else:
            reservation.status = 'CANCELLED'
            reservation.slot.status = 'AVAILABLE'
            db.session.commit()
            flash('Appointment cancelled. The time is open for someone else to book.', 'success')
    return redirect(url_for('customer_dashboard'))


@app.route('/api/openings')
def openings_api():
    slots = (AvailabilitySlot.query.join(Offering)
             .filter(Offering.active.is_(True), AvailabilitySlot.status == 'AVAILABLE',
                     AvailabilitySlot.starts_at > local_now())
             .order_by(AvailabilitySlot.starts_at).limit(100).all())
    return jsonify([{'offering': slot.offering.name, 'provider': slot.offering.provider.name,
                     'starts_at': slot.starts_at.isoformat(timespec='minutes'),
                     'url': url_for('offering_detail', offering_id=slot.offering_id)} for slot in slots])


@app.cli.command('seed')
def seed():
    """Add a demo provider, customer, services, and future appointment times."""
    provider = User.query.filter_by(email='admin@qflow.local').first()
    if not provider:
        provider = User(name='QFlow Provider', email='admin@qflow.local',
                        password=generate_password_hash(os.getenv('DEMO_PROVIDER_PASSWORD', 'ChangeMe123!')),
                        role='provider')
        db.session.add(provider)
        db.session.flush()
    if provider.role == 'admin':
        provider.role = 'provider'
    if not User.query.filter_by(email='customer@qflow.local').first():
        db.session.add(User(name='Demo Customer', email='customer@qflow.local',
                            password=generate_password_hash(os.getenv('DEMO_CUSTOMER_PASSWORD', 'ChangeMe123!')),
                            role='customer'))
    if not Offering.query.filter_by(provider_id=provider.id).first():
        first = Offering(provider_id=provider.id, name='Study skills session',
                         description='A one-to-one session to plan study routines and exam preparation.', duration_minutes=30)
        second = Offering(provider_id=provider.id, name='CV review',
                          description='Get practical feedback on your CV and next steps.', duration_minutes=45)
        db.session.add_all([first, second])
        db.session.flush()
        tomorrow = local_now().date() + timedelta(days=1)
        def at(hour, minute=0):
            return datetime.combine(tomorrow, datetime.min.time()).replace(hour=hour, minute=minute)
        db.session.add_all([
            AvailabilitySlot(offering_id=first.id, starts_at=at(10), ends_at=at(10, 30)),
            AvailabilitySlot(offering_id=first.id, starts_at=at(11), ends_at=at(11, 30)),
            AvailabilitySlot(offering_id=second.id, starts_at=at(13), ends_at=at(13, 45)),
        ])
    db.session.commit()
    print('Demo provider: admin@qflow.local / ChangeMe123!')
    print('Demo customer: customer@qflow.local / ChangeMe123!')


with app.app_context():
    db.create_all()

if __name__ == '__main__':
    app.run(debug=os.getenv('FLASK_DEBUG') == '1')
