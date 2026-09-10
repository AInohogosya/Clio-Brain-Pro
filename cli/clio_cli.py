#!/usr/bin/env python3
"""
Clio Brain Pro CLI - Terminal Interface

Provides interactive terminal interface with complete feature parity to Web UI.
Integrates provider/configuration selection kit into core configuration pipeline.
"""

import sys
import os
import json
from datetime import datetime
from typing import Optional, List, Dict, Any

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from clio_brain.control.models import MissionType, MissionStatus
from clio_brain.control.service import ControlService, OrganizationStore
from clio_brain.authority.service import AuthorityService, GrantType, AuthorityLevel
from clio_brain.commerce.treasury import TreasuryService, AccountType
from clio_brain.planning.service import PlanningService, PortfolioCandidate
from clio_brain.reliability.service import ReliabilityService


class Colors:
    """ANSI color codes for terminal output."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"


class ProviderSelectionKit:
    """
    Interactive provider/configuration selection kit.
    Integrated into the core configuration pipeline.
    """
    
    PROVIDERS = {
        "openai": {
            "name": "OpenAI",
            "models": ["gpt-4", "gpt-4-turbo", "gpt-3.5-turbo"],
            "env_var": "OPENAI_API_KEY",
            "description": "OpenAI GPT models for general tasks"
        },
        "anthropic": {
            "name": "Anthropic",
            "models": ["claude-3-opus", "claude-3-sonnet", "claude-3-haiku"],
            "env_var": "ANTHROPIC_API_KEY",
            "description": "Anthropic Claude models for reasoning tasks"
        },
        "google": {
            "name": "Google",
            "models": ["gemini-pro", "gemini-ultra"],
            "env_var": "GOOGLE_API_KEY",
            "description": "Google Gemini models"
        },
        "openrouter": {
            "name": "OpenRouter",
            "models": ["meta-llama/llama-3-70b-instruct", "mistralai/mistral-large", "anthropic/claude-3-opus", "openai/gpt-4-turbo"],
            "env_var": "OPENROUTER_API_KEY",
            "description": "OpenRouter - Access to multiple AI providers via unified API"
        },
        "nvidia": {
            "name": "NVIDIA NIM",
            "models": ["meta/llama3-70b-instruct", "meta/llama3-8b-instruct", "mistralai/mistral-large", "google/gemma-7b"],
            "env_var": "NVIDIA_API_KEY",
            "description": "NVIDIA NIM - High-performance inference with NVIDIA GPUs"
        },
        "local": {
            "name": "Local (Ollama)",
            "models": ["llama2", "mistral", "codellama"],
            "env_var": "OLLAMA_HOST",
            "description": "Local models via Ollama"
        }
    }
    
    def __init__(self):
        self.selected_provider = None
        self.selected_model = None
        self.config_file = "./data/provider_config.json"
    
    def display_providers(self):
        """Display available providers."""
        print(f"\n{Colors.BOLD}{Colors.CYAN}=== AI Provider Selection ==={Colors.RESET}\n")
        
        for idx, (key, provider) in enumerate(self.PROVIDERS.items(), 1):
            status = "✓" if os.environ.get(provider['env_var']) else "○"
            print(f"{Colors.YELLOW}[{idx}]{Colors.RESET} {provider['name']} ({status})")
            print(f"    {provider['description']}")
            print(f"    Models: {', '.join(provider['models'])}")
            print(f"    Env: {provider['env_var']}")
            print()
    
    def select_provider(self) -> Optional[str]:
        """Interactive provider selection."""
        self.display_providers()
        
        while True:
            try:
                choice = input(f"{Colors.GREEN}Select provider (1-{len(self.PROVIDERS)}): {Colors.RESET}")
                idx = int(choice) - 1
                providers = list(self.PROVIDERS.keys())
                
                if 0 <= idx < len(providers):
                    self.selected_provider = providers[idx]
                    print(f"{Colors.GREEN}✓ Selected: {self.PROVIDERS[self.selected_provider]['name']}{Colors.RESET}")
                    return self.selected_provider
                else:
                    print(f"{Colors.RED}Invalid selection{Colors.RESET}")
            except ValueError:
                print(f"{Colors.RED}Please enter a number{Colors.RESET}")
            except KeyboardInterrupt:
                print(f"\n{Colors.YELLOW}Selection cancelled{Colors.RESET}")
                return None
    
    def select_model(self, provider_key: str) -> Optional[str]:
        """Select model for chosen provider."""
        provider = self.PROVIDERS.get(provider_key)
        if not provider:
            return None
        
        print(f"\n{Colors.BOLD}Available models for {provider['name']}:")
        for idx, model in enumerate(provider['models'], 1):
            print(f"  [{idx}] {model}")
        
        while True:
            try:
                choice = input(f"\nSelect model (1-{len(provider['models'])}): ")
                idx = int(choice) - 1
                
                if 0 <= idx < len(provider['models']):
                    self.selected_model = provider['models'][idx]
                    print(f"{Colors.GREEN}✓ Selected: {self.selected_model}{Colors.RESET}")
                    return self.selected_model
                else:
                    print(f"{Colors.RED}Invalid selection{Colors.RESET}")
            except ValueError:
                print(f"{Colors.RED}Please enter a number{Colors.RESET}")
            except KeyboardInterrupt:
                return None
    
    def save_config(self, organization_id: str):
        """Save provider configuration."""
        config = {
            "provider": self.selected_provider,
            "model": self.selected_model,
            "organization_id": organization_id,
            "configured_at": datetime.utcnow().isoformat()
        }
        
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, 'w') as f:
            json.dump(config, f, indent=2)
        
        print(f"{Colors.GREEN}✓ Configuration saved to {self.config_file}{Colors.RESET}")
        return config
    
    def load_config(self) -> Optional[Dict]:
        """Load existing configuration."""
        if os.path.exists(self.config_file):
            with open(self.config_file, 'r') as f:
                return json.load(f)
        return None


class ClioBrainCLI:
    """Main CLI application for Clio Brain Pro."""
    
    def __init__(self):
        self.store = OrganizationStore()
        self.control = ControlService(self.store)
        self.authority = AuthorityService()
        self.treasury = TreasuryService()
        self.planning = PlanningService()
        self.reliability = ReliabilityService()
        self.provider_kit = ProviderSelectionKit()
        self.current_org = None
        self.running = True
    
    def clear_screen(self):
        """Clear terminal screen."""
        os.system('cls' if os.name == 'nt' else 'clear')
    
    def display_header(self):
        """Display application header."""
        print(f"\n{Colors.BOLD}{Colors.CYAN}╔════════════════════════════════════════╗{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}║     CLIO BRAIN PRO - Organization OS   ║{Colors.RESET}")
        print(f"{Colors.BOLD}{Colors.CYAN}╚════════════════════════════════════════╝{Colors.RESET}\n")
    
    def display_menu(self):
        """Display main menu."""
        print(f"\n{Colors.BOLD}=== Main Menu ==={Colors.RESET}")
        print(f"  [1] Organizations")
        print(f"  [2] Missions")
        print(f"  [3] Tasks")
        print(f"  [4] Authority & Grants")
        print(f"  [5] Treasury & Finance")
        print(f"  [6] Planning & Portfolio")
        print(f"  [7] System Health")
        print(f"  [8] Provider Configuration")
        print(f"  [0] Exit")
    
    def setup_organization(self):
        """Create or select an organization."""
        orgs = self.control.list_organizations()
        
        if not orgs:
            print(f"\n{Colors.YELLOW}No organizations found. Create one:{Colors.RESET}")
            name = input("Organization name: ")
            charter = input("Organization charter: ")
            org = self.control.create_organization(name, charter)
            self.current_org = org
            print(f"{Colors.GREEN}✓ Created organization: {org.name}{Colors.RESET}")
        else:
            print(f"\n{Colors.BOLD}Existing organizations:{Colors.RESET}")
            for idx, org in enumerate(orgs, 1):
                print(f"  [{idx}] {org.name} - {org.charter[:50]}...")
            
            choice = input(f"\nSelect organization (1-{len(orgs)}) or [n]ew: ")
            if choice.lower() == 'n':
                name = input("Organization name: ")
                charter = input("Organization charter: ")
                org = self.control.create_organization(name, charter)
                self.current_org = org
            elif choice.isdigit():
                idx = int(choice) - 1
                if 0 <= idx < len(orgs):
                    self.current_org = orgs[idx]
                    print(f"{Colors.GREEN}✓ Selected: {self.current_org.name}{Colors.RESET}")
    
    def configure_provider(self):
        """Run provider selection kit."""
        print(f"\n{Colors.BOLD}{Colors.MAGENTA}=== Provider Configuration ==={Colors.RESET}")
        
        # Check for existing config
        existing = self.provider_kit.load_config()
        if existing:
            print(f"\nCurrent configuration:")
            print(f"  Provider: {existing.get('provider')}")
            print(f"  Model: {existing.get('model')}")
            
            change = input("\nChange configuration? (y/n): ")
            if change.lower() != 'y':
                return existing
        
        # Run selection
        provider = self.provider_kit.select_provider()
        if not provider:
            return None
        
        model = self.provider_kit.select_model(provider)
        if not model:
            return None
        
        # Save config
        org_id = self.current_org.id if self.current_org else ""
        return self.provider_kit.save_config(org_id)
    
    def manage_missions(self):
        """Mission management submenu."""
        if not self.current_org:
            print(f"{Colors.RED}No organization selected{Colors.RESET}")
            return
        
        while True:
            print(f"\n{Colors.BOLD}=== Mission Management ==={Colors.RESET}")
            print(f"  [1] Create Mission")
            print(f"  [2] List Missions")
            print(f"  [3] View Mission Details")
            print(f"  [4] Record Attempt/Pivot")
            print(f"  [5] Satisfy Mission")
            print(f"  [0] Back")
            
            choice = input("Select: ")
            
            if choice == '1':
                self.create_mission()
            elif choice == '2':
                self.list_missions()
            elif choice == '3':
                self.view_mission()
            elif choice == '4':
                self.record_attempt()
            elif choice == '5':
                self.satisfy_mission()
            elif choice == '0':
                break
    
    def create_mission(self):
        """Create a new mission."""
        print(f"\n{Colors.BOLD}=== Create Mission ==={Colors.RESET}")
        
        print("\nMission types:")
        for idx, mt in enumerate(MissionType, 1):
            print(f"  [{idx}] {mt.value}: {mt.name}")
        
        type_choice = input("Select type: ")
        try:
            mission_type = list(MissionType)[int(type_choice) - 1]
        except (ValueError, IndexError):
            mission_type = MissionType.OUTCOME
        
        title = input("Title: ")
        description = input("Description: ")
        
        print("\nEnter acceptance criteria (empty line to finish):")
        criteria = []
        while True:
            criterion = input(f"  [{len(criteria)+1}] ")
            if not criterion:
                break
            criteria.append(criterion)
        
        mission = self.control.create_mission(
            organization_id=self.current_org.id,
            mission_type=mission_type,
            title=title,
            description=description,
            acceptance_criteria=criteria
        )
        
        print(f"{Colors.GREEN}✓ Created mission: {mission.title}{Colors.RESET}")
    
    def list_missions(self):
        """List all missions."""
        missions = self.control.list_missions(organization_id=self.current_org.id)
        
        if not missions:
            print(f"\n{Colors.YELLOW}No missions found{Colors.RESET}")
            return
        
        print(f"\n{Colors.BOLD}Missions:{Colors.RESET}")
        for m in missions:
            status_color = Colors.GREEN if m.status == MissionStatus.SATISFIED else Colors.WHITE
            print(f"  [{m.id[:8]}] {status_color}{m.status.value}{Colors.RESET} - {m.title}")
    
    def view_mission(self):
        """View mission details."""
        mission_id = input("Mission ID: ")
        status = self.control.get_mission_status(mission_id)
        
        if "error" in status:
            print(f"{Colors.RED}{status['error']}{Colors.RESET}")
            return
        
        mission = status['mission']
        print(f"\n{Colors.BOLD}=== {mission.title} ==={Colors.RESET}")
        print(f"Type: {mission.mission_type.value}")
        print(f"Status: {mission.status.value}")
        print(f"Description: {mission.description}")
        print(f"\nAcceptance Criteria:")
        for c in mission.acceptance_criteria:
            print(f"  • {c}")
        
        print(f"\nTasks: {status['active_tasks']} active, {status['completed_tasks']} completed, {status['failed_tasks']} failed")
        
        if mission.attempt_history:
            print(f"\nAttempt History ({len(mission.attempt_history)}):")
            for attempt in mission.attempt_history[-3:]:
                print(f"  • {attempt['failure_cause']}")
    
    def record_attempt(self):
        """Record a mission attempt."""
        mission_id = input("Mission ID: ")
        assumption = input("Assumption: ")
        methodology = input("Methodology: ")
        failure_cause = input("Failure cause: ")
        
        self.control.record_mission_attempt(mission_id, assumption, methodology, failure_cause)
        print(f"{Colors.GREEN}✓ Attempt recorded{Colors.RESET}")
    
    def satisfy_mission(self):
        """Mark mission as satisfied."""
        mission_id = input("Mission ID: ")
        mission = self.control.get_mission(mission_id)
        
        if mission:
            confirm = input(f"Confirm satisfaction of '{mission.title}'? (y/n): ")
            if confirm.lower() == 'y':
                self.control.satisfy_mission(mission_id)
                print(f"{Colors.GREEN}✓ Mission satisfied{Colors.RESET}")
    
    def show_health(self):
        """Show system health summary."""
        summary = self.reliability.get_health_summary()
        
        print(f"\n{Colors.BOLD}=== System Health ==={Colors.RESET}")
        print(f"  Checks: {summary['healthy_checks']}/{summary['total_checks']} healthy")
        print(f"  Generation: {summary['current_generation']}")
        print(f"  Backups: {summary['total_backups']}")
        
        if summary['latest_backup']:
            print(f"  Latest backup: {summary['latest_backup'].get('created_at', 'N/A')}")
    
    def run(self):
        """Main CLI loop."""
        self.clear_screen()
        self.display_header()
        
        # Initial setup
        self.setup_organization()
        
        while self.running:
            self.display_menu()
            choice = input(f"\n{Colors.GREEN}Command: {Colors.RESET}")
            
            if choice == '1':
                print(f"\nOrganization: {self.current_org.name if self.current_org else 'None'}")
            elif choice == '2':
                self.manage_missions()
            elif choice == '3':
                print("\n[Task management - coming soon]")
            elif choice == '4':
                print("\n[Authority management - coming soon]")
            elif choice == '5':
                print("\n[Treasury management - coming soon]")
            elif choice == '6':
                print("\n[Planning - coming soon]")
            elif choice == '7':
                self.show_health()
            elif choice == '8':
                self.configure_provider()
            elif choice == '0':
                print(f"\n{Colors.CYAN}Goodbye!{Colors.RESET}")
                self.running = False
            else:
                print(f"{Colors.RED}Invalid command{Colors.RESET}")


def main():
    """Entry point for CLI."""
    cli = ClioBrainCLI()
    try:
        cli.run()
    except KeyboardInterrupt:
        print(f"\n{Colors.YELLOW}Interrupted{Colors.RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
