from extensions import db

class WazuhConfig(db.Model):
    """Конфигурация интеграции с Wazuh (заглушка для совместимости)"""
    __tablename__ = 'wazuh_config'
    
    id = db.Column(db.Integer, primary_key=True)
    api_url = db.Column(db.String(255))
    api_key = db.Column(db.String(255))
    enabled = db.Column(db.Boolean, default=False)
    
    def to_dict(self):
        return {
            'id': self.id,
            'api_url': self.api_url,
            'enabled': self.enabled
        }

class OsqueryInventory(db.Model):
    """Инвентаризация данных Osquery (заглушка для совместимости)"""
    __tablename__ = 'osquery_inventory'
    
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id', ondelete='CASCADE'), nullable=False, index=True)
        
    hostname = db.Column(db.String(255))
    os_version = db.Column(db.String(100))
    platform = db.Column(db.String(50))
    hardware_model = db.Column(db.String(200))
    cpu_brand = db.Column(db.String(200))
    physical_memory = db.Column(db.BigInteger) # в байтах
    
    last_seen = db.Column(db.DateTime)
    
    asset = db.relationship('Asset', back_populates='osquery_data')