import os
from datetime import datetime
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__, instance_relative_config=True)
os.makedirs(app.instance_path, exist_ok=True)
app.config.update(SECRET_KEY=os.getenv('SECRET_KEY', 'dev-only-change-me'), SQLALCHEMY_DATABASE_URI='sqlite:///' + os.path.join(app.instance_path, 'qflow.db'), SQLALCHEMY_TRACK_MODIFICATIONS=False)
db = SQLAlchemy(app)
csrf = CSRFProtect(app)

class User(db.Model):
    id=db.Column(db.Integer, primary_key=True); name=db.Column(db.String(100), nullable=False); email=db.Column(db.String(160), unique=True, nullable=False); password=db.Column(db.String(255), nullable=False); role=db.Column(db.String(12), default='user', nullable=False)
class Service(db.Model):
    id=db.Column(db.Integer, primary_key=True); name=db.Column(db.String(100), unique=True, nullable=False); prefix=db.Column(db.String(5), unique=True, nullable=False); avg_minutes=db.Column(db.Integer, default=5, nullable=False); active=db.Column(db.Boolean, default=True, nullable=False)
class Counter(db.Model):
    id=db.Column(db.Integer, primary_key=True); name=db.Column(db.String(80), nullable=False); service_id=db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False); active=db.Column(db.Boolean, default=True, nullable=False); service=db.relationship(Service)
class Token(db.Model):
    id=db.Column(db.Integer, primary_key=True); number=db.Column(db.String(20), nullable=False); sequence=db.Column(db.Integer, nullable=False); user_id=db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False); service_id=db.Column(db.Integer, db.ForeignKey('service.id'), nullable=False); counter_id=db.Column(db.Integer, db.ForeignKey('counter.id')); status=db.Column(db.String(12), default='WAITING', nullable=False); created=db.Column(db.DateTime, default=datetime.utcnow, nullable=False); called=db.Column(db.DateTime); updated=db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow); user=db.relationship(User); service=db.relationship(Service); counter=db.relationship(Counter)
    __table_args__=(db.UniqueConstraint('service_id','sequence'),)
class Notice(db.Model):
    id=db.Column(db.Integer, primary_key=True); user_id=db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False); message=db.Column(db.String(240), nullable=False); created=db.Column(db.DateTime, default=datetime.utcnow); read=db.Column(db.Boolean, default=False)

ACTIVE=('WAITING','CALLED','SERVING')
def current_user(): return db.session.get(User, session.get('uid'))
def login_required(f):
    @wraps(f)
    def w(*a,**k):
        if not current_user(): return redirect(url_for('login'))
        return f(*a,**k)
    return w
def admin_required(f):
    @wraps(f)
    def w(*a,**k):
        if not current_user() or current_user().role!='admin': abort(403)
        return f(*a,**k)
    return w
def pos(t):
    ahead=Token.query.filter(Token.service_id==t.service_id,Token.status=='WAITING',Token.created<t.created).count()
    workload=Token.query.filter(Token.service_id==t.service_id,Token.status.in_(('CALLED','SERVING'))).count()
    counters=max(1,Counter.query.filter_by(service_id=t.service_id,active=True).count())
    return ahead, round((ahead+workload)*t.service.avg_minutes/counters)
def notify(user_id, message): db.session.add(Notice(user_id=user_id,message=message))

@app.route('/')
def home(): return render_template('home.html')
@app.route('/register', methods=['GET','POST'])
def register():
    if request.method=='POST':
        name=request.form.get('name','').strip(); email=request.form.get('email','').strip().lower(); password=request.form.get('password','')
        if not name or len(password)<8 or User.query.filter_by(email=email).first(): flash('Use a name, a valid email, and a password of at least 8 characters. Email must be new.','error')
        else:
            db.session.add(User(name=name,email=email,password=generate_password_hash(password))); db.session.commit(); flash('Account created. You can sign in now.','success'); return redirect(url_for('login'))
    return render_template('auth.html',register=True)
@app.route('/login', methods=['GET','POST'])
def login():
    if request.method=='POST':
        u=User.query.filter_by(email=request.form.get('email','').strip().lower()).first()
        if u and check_password_hash(u.password,request.form.get('password','')): session.clear(); session['uid']=u.id; return redirect(url_for('admin') if u.role=='admin' else url_for('dashboard'))
        flash('That email and password did not match.','error')
    return render_template('auth.html',register=False)
@app.route('/logout',methods=['POST'])
@login_required
def logout(): session.clear(); return redirect(url_for('home'))
@app.route('/dashboard')
@login_required
def dashboard(): return render_template('dashboard.html',user=current_user(),services=Service.query.filter_by(active=True).all(),tokens=Token.query.filter_by(user_id=current_user().id).order_by(Token.created.desc()).limit(30).all())
@app.route('/token',methods=['POST'])
@login_required
def new_token():
    s=db.session.get(Service,request.form.get('service_id',type=int))
    if not s or not s.active: flash('Choose an available service.','error')
    elif Token.query.filter(Token.user_id==current_user().id,Token.service_id==s.id,Token.status.in_(ACTIVE)).first(): flash('You already have an active token for this service.','error')
    else:
        seq=(db.session.query(db.func.max(Token.sequence)).filter_by(service_id=s.id).scalar() or 0)+1
        counters=Counter.query.filter_by(service_id=s.id,active=True).all()
        counter=min(counters,key=lambda c: Token.query.filter_by(counter_id=c.id,status='WAITING').count()) if counters else None
        t=Token(number=f'{s.prefix}-{seq:03}',sequence=seq,user_id=current_user().id,service_id=s.id,counter_id=counter.id if counter else None)
        db.session.add(t); db.session.commit(); flash(f'Token {t.number} is ready. Estimated wait: {pos(t)[1]} min.','success')
    return redirect(url_for('dashboard'))
@app.route('/token/<int:tid>/cancel',methods=['POST'])
@login_required
def cancel_token(tid):
    t=db.get_or_404(Token,tid)
    if t.user_id!=current_user().id: abort(403)
    if t.status in ('WAITING','CALLED'): t.status='CANCELLED'; db.session.commit()
    return redirect(url_for('dashboard'))
@app.route('/api/my-queue')
@login_required
def my_queue():
    data=[]
    for t in Token.query.filter_by(user_id=current_user().id).filter(Token.status.in_(ACTIVE)).all():
        ahead,wait=pos(t); data.append(dict(id=t.id,number=t.number,status=t.status,ahead=ahead,wait=wait,service=t.service.name,counter=t.counter.name if t.counter else 'Unassigned',updated=t.updated.strftime('%H:%M:%S')))
        if ahead<=2 and t.status=='WAITING' and not Notice.query.filter_by(user_id=t.user_id,message=f'{t.number} is approaching').first(): notify(t.user_id,f'{t.number} is approaching')
    db.session.commit(); return jsonify(data)
@app.route('/api/notices')
@login_required
def notices(): return jsonify([dict(message=n.message,created=n.created.strftime('%H:%M')) for n in Notice.query.filter_by(user_id=current_user().id,read=False).order_by(Notice.created.desc()).limit(10)])
@app.route('/admin')
@admin_required
def admin(): return render_template('admin.html',tokens=Token.query.filter(Token.status.in_(ACTIVE)).order_by(Token.created).all(),counters=Counter.query.all(),stats={x:Token.query.filter_by(status=x).count() for x in ('WAITING','SERVING','COMPLETED','SKIPPED')})
@app.route('/admin/action/<int:tid>/<action>',methods=['POST'])
@admin_required
def action(tid,action):
    t=db.get_or_404(Token,tid)
    allowed={'call':('WAITING','CALLED'),'complete':(('CALLED','SERVING'),'COMPLETED'),'skip':(('CALLED','SERVING'),'SKIPPED'),'recall':('SKIPPED','WAITING'),'cancel':(('WAITING','CALLED'),'CANCELLED')}
    if action not in allowed: abort(400)
    old,new=allowed[action]; old=(old,) if isinstance(old,str) else old
    if t.status in old:
        t.status=new
        if new=='CALLED': t.called=datetime.utcnow(); notify(t.user_id,f'{t.number} has been called at {t.counter.name if t.counter else "the counter"}')
        elif new=='SKIPPED': notify(t.user_id,f'{t.number} was skipped. Please contact the service desk.')
        elif new=='COMPLETED': t.counter_id=None
        db.session.commit()
    return redirect(url_for('admin'))
@app.route('/admin/counter/<int:cid>/toggle',methods=['POST'])
@admin_required
def toggle(cid):
    c=db.get_or_404(Counter,cid); c.active=not c.active; db.session.commit(); return redirect(url_for('admin'))
@app.route('/display')
def display(): return render_template('display.html')
@app.route('/api/display')
def display_data():
    ts=Token.query.filter(Token.status.in_(('CALLED','SERVING','WAITING'))).order_by(Token.created).all()
    return jsonify([dict(number=t.number,service=t.service.name,counter=t.counter.name if t.counter else '—',status=t.status) for t in ts])
@app.route('/analytics')
@admin_required
def analytics():
    services=Service.query.all(); return render_template('analytics.html',labels=[s.name for s in services],counts=[Token.query.filter_by(service_id=s.id).count() for s in services],done=Token.query.filter_by(status='COMPLETED').count(),skipped=Token.query.filter_by(status='SKIPPED').count())
@app.cli.command('seed')
def seed():
    """Create sample departments, counters, and a demo admin (change its password)."""
    if not Service.query.first():
        for name,prefix in [('Examination Section','EX'),('Accounts Department','AC'),('Library','LIB'),('Administration Office','ADM'),('Student Support','SS')]:
            s=Service(name=name,prefix=prefix,avg_minutes=6); db.session.add(s); db.session.flush(); db.session.add(Counter(name=f'{prefix} Counter 1',service_id=s.id))
    if not User.query.filter_by(email='admin@qflow.local').first(): db.session.add(User(name='QFlow Admin',email='admin@qflow.local',password=generate_password_hash(os.getenv('DEMO_ADMIN_PASSWORD','ChangeMe123!')),role='admin'))
    db.session.commit(); print('Seeded. Demo login: admin@qflow.local / ChangeMe123! (change it before sharing).')
with app.app_context(): db.create_all()
@app.context_processor
def inject_user():
    return {'current_user': current_user()}
if __name__=='__main__': app.run(debug=os.getenv('FLASK_DEBUG')=='1')

