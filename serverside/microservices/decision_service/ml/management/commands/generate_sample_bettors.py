"""Django management command to generate sample bettor profiles for testing ML models."""
from django.core.management.base import BaseCommand, CommandError
from ...models import BettorProfile
import numpy as np
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Generate sample bettor profiles for ML model testing'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--count',
            type=int,
            default=100,
            help='Number of sample bettors to generate (default: 100)'
        )
        
        parser.add_argument(
            '--seed',
            type=int,
            default=42,
            help='Random seed for reproducibility (default: 42)'
        )
        
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing bettor profiles before generating'
        )
    
    def handle(self, *args, **options):
        count = options['count']
        seed = options['seed']
        clear = options['clear']
        
        if clear:
            self.stdout.write('Clearing existing bettor profiles...')
            BettorProfile.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✓ Profiles cleared'))
        
        np.random.seed(seed)
        
        self.stdout.write(
            self.style.SUCCESS(f'Generating {count} sample bettor profiles...')
        )
        
        profiles = []
        for i in range(count):
            profile = self._generate_bettor_profile(i)
            profiles.append(profile)
        
        created_profiles = BettorProfile.objects.bulk_create(profiles)
        
        self.stdout.write(self.style.SUCCESS(f'\n✓ Successfully created {len(created_profiles)} bettor profiles!'))
        self._print_statistics(created_profiles)
    
    def _generate_bettor_profile(self, index: int) -> BettorProfile:
        """Generate a realistic sample bettor profile."""
        profile_type = np.random.choice(['expert', 'intermediate', 'novice', 'aggressive', 'conservative'])
        
        if profile_type == 'expert':
            win_rate = np.random.uniform(0.55, 0.75)
            strategy_diversity = np.random.uniform(0.5, 1.0)
            roi = np.random.uniform(0.1, 0.5)
            average_bet = np.random.uniform(100, 500)
        elif profile_type == 'intermediate':
            win_rate = np.random.uniform(0.45, 0.55)
            strategy_diversity = np.random.uniform(0.4, 0.8)
            roi = np.random.uniform(-0.1, 0.2)
            average_bet = np.random.uniform(50, 200)
        elif profile_type == 'novice':
            win_rate = np.random.uniform(0.35, 0.50)
            strategy_diversity = np.random.uniform(0.2, 0.5)
            roi = np.random.uniform(-0.3, 0.0)
            average_bet = np.random.uniform(20, 100)
        elif profile_type == 'aggressive':
            win_rate = np.random.uniform(0.40, 0.60)
            strategy_diversity = np.random.uniform(0.3, 0.7)
            roi = np.random.uniform(-0.2, 0.3)
            average_bet = np.random.uniform(200, 1000)
        else:  # conservative
            win_rate = np.random.uniform(0.48, 0.52)
            strategy_diversity = np.random.uniform(0.2, 0.4)
            roi = np.random.uniform(-0.05, 0.1)
            average_bet = np.random.uniform(10, 50)
        
        total_bets = np.random.randint(50, 1000)
        total_wins = int(total_bets * win_rate)
        total_losses = total_bets - total_wins
        
        max_bet = average_bet * np.random.uniform(1.5, 3.0)
        min_bet = average_bet * np.random.uniform(0.2, 0.8)
        bet_variance = (average_bet ** 2) * np.random.uniform(0.1, 1.0)
        
        average_bets_per_round = np.random.uniform(1, 10)
        total_active_rounds = max(1, int(total_bets / average_bets_per_round))
        
        total_profit = (average_bet * total_bets) * (roi / 100)
        
        return BettorProfile(
            bettor_id=f'bettor_{index:06d}_{profile_type}',
            total_bets=total_bets,
            total_wins=total_wins,
            total_losses=total_losses,
            win_rate=float(win_rate),
            average_bet_amount=float(average_bet),
            max_bet_amount=float(max_bet),
            min_bet_amount=float(min_bet),
            bet_variance=float(bet_variance),
            average_bets_per_round=float(average_bets_per_round),
            total_active_rounds=total_active_rounds,
            favorite_bet_type=np.random.choice(['conservative', 'moderate', 'aggressive']),
            strategy_diversity=float(strategy_diversity),
            total_profit=float(total_profit),
            roi=float(roi),
        )
    
    def _print_statistics(self, profiles):
        """Print summary statistics of generated profiles."""
        win_rates = [p.win_rate for p in profiles]
        rois = [p.roi for p in profiles]
        bet_amounts = [p.average_bet_amount for p in profiles]
        
        self.stdout.write('\nSample Statistics:')
        self.stdout.write(f'  Win Rate: {np.mean(win_rates):.2%} ± {np.std(win_rates):.2%}')
        self.stdout.write(f'  ROI: {np.mean(rois):.2%} ± {np.std(rois):.2%}')
        self.stdout.write(f'  Avg Bet Amount: ${np.mean(bet_amounts):.2f} ± ${np.std(bet_amounts):.2f}')
        self.stdout.write(f'  Total Bets: {sum(p.total_bets for p in profiles):,}')
