from datetime import datetime
from extensions import db
from utils import MOSCOW_TZ

class ServiceInventory(db.Model):
    """Детальная информация о сервисах на портах"""
    __tablename__ = 'service_inventory'
    
    id = db.Column(db.Integer, primary_key=True)
    asset_id = db.Column(db.Integer, db.ForeignKey('asset.id'), nullable=False, index=True)
    
    port = db.Column(db.Integer, nullable=False)
    protocol = db.Column(db.String(10), default='tcp') # tcp, udp
    state = db.Column(db.String(20), default='open') # open, closed, filtered
    service_name = db.Column(db.String(100)) # http, ssh, mysql
    product = db.Column(db.String(200)) # Apache httpd
    version = db.Column(db.String(200)) # 2.4.41
    extra_info = db.Column(db.String(200)) # Ubuntu
    script_output = db.Column(db.Text) # Вывод скриптов nmap
    
    # SSL сертификат (если есть)
    ssl_subject = db.Column(db.String(500))
    ssl_issuer = db.Column(db.String(500))
    ssl_not_before = db.Column(db.DateTime)
    ssl_not_after = db.Column(db.DateTime)
    
    discovered_at = db.Column(db.DateTime, default=lambda: datetime.now(MOSCOW_TZ))
    
    asset = db.relationship('Asset', back_populates='services')
    
    def to_dict(self):
        return {
            'id': self.id,
            'port': self.port,
            'protocol': self.protocol,
            'state': self.state,
            'service_name': self.service_name,
            'product': self.product,
            'version': self.version,
            'extra_info': self.extra_info,
            'script_output': self.script_output,
            'ssl_info': {
                'subject': self.ssl_subject,
                'issuer': self.ssl_issuer,
                'not_before': self.ssl_not_before.isoformat() if self.ssl_not_before else None,
                'not_after': self.ssl_not_after.isoformat() if self.ssl_not_after else None
            } if self.ssl_subject else None,
            'discovered_at': self.discovered_at.isoformat() if self.discovered_at else None
        }