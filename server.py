#!/usr/bin/env python3
"""
Clio Brain Pro - Main Application Server

Single-command launch via start.sh that starts the local host server
with both Web UI and API endpoints.
"""

import sys
import os
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from clio_brain.control.models import MissionType, MissionStatus
from clio_brain.control.service import ControlService, OrganizationStore
from clio_brain.authority.service import AuthorityService, GrantType, AuthorityLevel
from clio_brain.commerce.treasury import TreasuryService, AccountType
from clio_brain.planning.service import PlanningService
from clio_brain.reliability.service import ReliabilityService


class ClioBrainAPI:
    """API handler for Clio Brain services."""
    
    def __init__(self):
        self.store = OrganizationStore()
        self.control = ControlService(self.store)
        self.authority = AuthorityService()
        self.treasury = TreasuryService()
        self.planning = PlanningService()
        self.reliability = ReliabilityService()
        
        # Initialize with default grants if none exist
        self._initialize_default_grants()
    
    def _initialize_default_grants(self):
        """Create default standing grants for new organizations."""
        orgs = self.control.list_organizations()
        for org in orgs:
            existing = self.authority.list_grants(org.id)
            if not existing:
                # Development grant
                self.authority.create_grant(
                    organization_id=org.id,
                    grant_type=GrantType.DEVELOPMENT,
                    name="Development Grant",
                    description="Autonomous development operations",
                    authority_level=AuthorityLevel.AUTONOMOUS,
                    resource_limits={"compute_hours": 100, "usd": 500},
                    allowed_operations=["repo_create", "code_write", "test_run"]
                )
                
                # Research grant
                self.authority.create_grant(
                    organization_id=org.id,
                    grant_type=GrantType.RESEARCH,
                    name="Research Grant",
                    description="Information gathering and analysis",
                    authority_level=AuthorityLevel.AUTONOMOUS,
                    resource_limits={"api_calls": 1000, "usd": 100}
                )


api = ClioBrainAPI()


class APIHandler(SimpleHTTPRequestHandler):
    """HTTP request handler with API routing."""
    
    def __init__(self, *args, **kwargs):
        # Serve static files from web/ directory
        super().__init__(*args, directory=os.path.join(os.path.dirname(__file__), 'web'), **kwargs)
    
    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        
        # API routes
        if parsed.path.startswith('/api/'):
            self.handle_api_get(parsed.path)
        else:
            # Serve static files from web/ directory
            if parsed.path == '/' or parsed.path == '':
                self.path = '/index.html'
            super().do_GET()
    
    def do_POST(self):
        """Handle POST requests."""
        parsed = urlparse(self.path)
        
        if parsed.path.startswith('/api/'):
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(body) if body else {}
            self.handle_api_post(parsed.path, data)
        else:
            self.send_error(404, "Not Found")
    
    def handle_api_get(self, path):
        """Handle API GET requests."""
        try:
            if path == '/api/organizations':
                orgs = api.control.list_organizations()
                self.send_json([self.serialize_org(o) for o in orgs])
            
            elif path == '/api/missions':
                missions = api.control.list_missions()
                self.send_json([self.serialize_mission(m) for m in missions])
            
            elif path == '/api/health':
                summary = api.reliability.get_health_summary()
                self.send_json(summary)
            
            elif path.startswith('/api/missions/'):
                mission_id = path.split('/')[-1]
                status = api.control.get_mission_status(mission_id)
                self.send_json(status)
            
            elif path == '/api/grants':
                grants = api.authority.list_grants()
                self.send_json([self.serialize_grant(g) for g in grants])
            
            elif path == '/api/treasury':
                orgs = api.control.list_organizations()
                treasury_data = []
                for org in orgs:
                    total = api.treasury.get_total_revenue(org.id)
                    tier = api.treasury.get_revenue_tier(org.id)
                    treasury_data.append({
                        'organization_id': org.id,
                        'total_revenue': total,
                        'tier': tier
                    })
                self.send_json(treasury_data)
            
            else:
                self.send_error(404, "API endpoint not found")
        
        except Exception as e:
            self.send_error(500, str(e))
    
    def handle_api_post(self, path, data):
        """Handle API POST requests."""
        try:
            if path == '/api/organizations':
                org = api.control.create_organization(
                    name=data.get('name', 'Unnamed'),
                    charter=data.get('charter', '')
                )
                self.send_json(self.serialize_org(org), status=201)
                
                # Create default grants
                api.authority.create_grant(
                    organization_id=org.id,
                    grant_type=GrantType.DEVELOPMENT,
                    name="Development Grant",
                    description="Autonomous development operations",
                    authority_level=AuthorityLevel.AUTONOMOUS,
                    resource_limits={"compute_hours": 100, "usd": 500}
                )
            
            elif path == '/api/missions':
                mission = api.control.create_mission(
                    organization_id=data.get('organization_id'),
                    mission_type=MissionType(data.get('mission_type', 'outcome')),
                    title=data.get('title', 'Untitled'),
                    description=data.get('description', ''),
                    acceptance_criteria=data.get('acceptance_criteria', [])
                )
                self.send_json(self.serialize_mission(mission), status=201)
            
            elif path == '/api/config/provider':
                config = {
                    'provider': data.get('provider'),
                    'model': data.get('model'),
                    'configured_at': __import__('datetime').datetime.utcnow().isoformat()
                }
                os.makedirs('./data', exist_ok=True)
                with open('./data/provider_config.json', 'w') as f:
                    json.dump(config, f, indent=2)
                self.send_json({'status': 'saved'})
            
            elif path.startswith('/api/missions/') and path.endswith('/satisfy'):
                mission_id = path.split('/')[3]
                api.control.satisfy_mission(mission_id)
                self.send_json({'status': 'satisfied'})
            
            elif path.startswith('/api/missions/') and path.endswith('/cancel'):
                mission_id = path.split('/')[3]
                api.control.cancel_mission(mission_id)
                self.send_json({'status': 'cancelled'})
            
            else:
                self.send_error(404, "API endpoint not found")
        
        except Exception as e:
            self.send_error(500, str(e))
    
    def serialize_org(self, org):
        """Serialize organization to JSON-safe dict."""
        return {
            'id': org.id,
            'name': org.name,
            'charter': org.charter,
            'created_at': org.created_at.isoformat() if hasattr(org.created_at, 'isoformat') else str(org.created_at),
            'roles': org.roles,
            'budgets': org.budgets
        }
    
    def serialize_mission(self, mission):
        """Serialize mission to JSON-safe dict."""
        return {
            'id': mission.id,
            'organization_id': mission.organization_id,
            'mission_type': mission.mission_type.value if hasattr(mission.mission_type, 'value') else str(mission.mission_type),
            'title': mission.title,
            'description': mission.description,
            'status': mission.status.value if hasattr(mission.status, 'value') else str(mission.status),
            'acceptance_criteria': mission.acceptance_criteria,
            'created_at': mission.created_at.isoformat() if hasattr(mission.created_at, 'isoformat') else str(mission.created_at)
        }
    
    def serialize_grant(self, grant):
        """Serialize grant to JSON-safe dict."""
        return {
            'id': grant.id,
            'organization_id': grant.organization_id,
            'grant_type': grant.grant_type.value if hasattr(grant.grant_type, 'value') else str(grant.grant_type),
            'name': grant.name,
            'description': grant.description,
            'authority_level': grant.authority_level.value if hasattr(grant.authority_level, 'value') else str(grant.authority_level),
            'is_active': grant.is_active
        }
    
    def send_json(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def send_error(self, code, message):
        """Send error response."""
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'error': message}).encode())
    
    def log_message(self, format, *args):
        """Override to customize logging."""
        print(f"[{self.log_date_time_string()}] {args[0]}")


def run_server(port=8080):
    """Run the HTTP server."""
    server_address = ('', port)
    httpd = HTTPServer(server_address, APIHandler)
    
    print(f"\n\033[96m╔════════════════════════════════════════╗\033[0m")
    print(f"\033[96m║     CLIO BRAIN PRO - Server Running    ║\033[0m")
    print(f"\033[96m╚════════════════════════════════════════╝\033[0m")
    print(f"\n  Web UI:   http://localhost:{port}")
    print(f"  API:      http://localhost:{port}/api/")
    print(f"\n  Press Ctrl+C to stop\n")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n\nShutting down...")
        httpd.shutdown()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run_server(port)
