from datetime import datetime
from extensions import db
from utils import MOSCOW_TZ

# Таблица многие-ко-многим для связи Активов и Групп
asset_groups = db.Table('asset_groups',
    db.Column('asset_id', db.Integer, db.ForeignKey('asset.id', ondelete='CASCADE'), primary_key=True),
    db.Column('group_id', db.Integer, db.ForeignKey('asset_group.id', ondelete='CASCADE'), primary_key=True)
)