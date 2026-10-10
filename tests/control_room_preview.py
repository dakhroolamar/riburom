"""Loopback-only, in-memory visual fixture; never production data."""
import json
import os
from datetime import date, timedelta
from tests.ui_preview import app, db
from flask import abort, redirect, request, session
from werkzeug.security import generate_password_hash
from models import User, Message, SiteSettings
from control_room_models import LeadWorkspace, Trip, TripUpdate

with app.app_context():
    settings = SiteSettings.query.first()
    settings.hero_logo = 'control-room/brand.svg'
    settings.header_mark = 'control-room/brand.svg'
    settings.header_wordmark = 'control-room/brand.svg'
    owner = User(username='preview', full_name='Preview Admin', role='owner',
                 password_hash=generate_password_hash('preview-only-password'))
    db.session.add(owner)
    db.session.flush()
    for index, name in enumerate(['Sharma Family', 'The Wanderers Club', 'Mehta Group',
                                 'Singh Family', 'Aditi & Karan', 'Global Horizons',
                                 'Karthik Iyer', 'Lee Family', 'Travelog Expeditions', 'Neha Kapoor']):
        message = Message(name=name, email=f'preview-{index}@example.com',
            travellers='4 Adults', travel_dates='12 – 15 Oct 2026',
            tour_interest='Shillong, Cherrapunji, Mawlynnong',
            message='Local visual fixture: family holiday, nature and local culture.')
        db.session.add(message)
        db.session.flush()
        db.session.add(LeadWorkspace(source='website', source_id=message.id,
            status=['NEW','CONTACTED','QUOTED','CONFIRMED','CLOSED'][index % 5],
            assigned_user_id=owner.id, budget=80000))
        if index < 5:
            trip = Trip(name=name, destination='Shillong – Cherrapunji – Living Root Bridges',
                start_date=date.today()+timedelta(days=index), end_date=date.today()+timedelta(days=index+3),
                travellers=4+index, status=['IN_PROGRESS','CONFIRMED','PLANNED'][index % 3],
                guide='Preview Guide', driver='Preview Driver', vehicle='Innova · Preview',
                itinerary_json=json.dumps(['Shillong Arrival & City Tour','Cherrapunji – Waterfalls & Caves','Nongriat Trek – Living Root Bridge','Return to Shillong']),
                accommodation_json=json.dumps(['The Loft · Shillong · 4 rooms','Polo Orchid · Cherrapunji · 4 rooms']),
                checklist_json=json.dumps({'Guide briefed on itinerary':True}))
            db.session.add(trip)
    db.session.commit()

@app.get('/__visual/control')
def control_preview_login():
    if request.remote_addr not in ('127.0.0.1', '::1'):
        abort(403)
    with app.app_context():
        owner = User.query.filter_by(username='preview').one()
        session['user_id'] = owner.id
        session['session_version'] = owner.session_version
    return redirect('/workspace/control/overview')

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.environ.get('OPERATIONS_PREVIEW_PORT','5055')), use_reloader=False, threaded=False)
