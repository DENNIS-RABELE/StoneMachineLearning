"""Data preprocessing and aggregation utilities for bettor profile generation."""
from django.utils import timezone
from datetime import timedelta
from typing import Dict, List, Tuple, Optional
import numpy as np
import logging

from ..models import BettorProfile

logger = logging.getLogger(__name__)


class BettorDataAggregator:
    """Aggregates betting data from various sources into bettor profiles."""
    
    @staticmethod
    def update_bettor_profile_from_betting_history(
        bettor_id: str,
        betting_history: List[Dict],
        time_window_days: Optional[int] = None
    ) -> BettorProfile:
        """Update or create a bettor profile from their betting history."""
        if time_window_days:
            cutoff_date = timezone.now() - timedelta(days=time_window_days)
            betting_history = [
                bet for bet in betting_history
                if bet.get('timestamp') and bet['timestamp'] >= cutoff_date
            ]
        
        stats = BettorDataAggregator._calculate_betting_stats(betting_history)
        
        profile, created = BettorProfile.objects.update_or_create(
            bettor_id=bettor_id,
            defaults={
                'total_bets': stats['total_bets'],
                'total_wins': stats['total_wins'],
                'total_losses': stats['total_losses'],
                'win_rate': stats['win_rate'],
                'average_bet_amount': stats['average_bet_amount'],
                'max_bet_amount': stats['max_bet_amount'],
                'min_bet_amount': stats['min_bet_amount'],
                'bet_variance': stats['bet_variance'],
                'average_bets_per_round': stats['average_bets_per_round'],
                'total_active_rounds': stats['total_active_rounds'],
                'favorite_bet_type': stats['favorite_bet_type'],
                'strategy_diversity': stats['strategy_diversity'],
                'total_profit': stats['total_profit'],
                'roi': stats['roi'],
            }
        )
        return profile
    
    @staticmethod
    def _calculate_betting_stats(betting_history: List[Dict]) -> Dict:
        """Calculate statistical features from betting history."""
        if not betting_history:
            return {
                'total_bets': 0, 'total_wins': 0, 'total_losses': 0,
                'win_rate': 0.0, 'average_bet_amount': 0.0,
                'max_bet_amount': 0.0, 'min_bet_amount': 0.0,
                'bet_variance': 0.0, 'average_bets_per_round': 0.0,
                'total_active_rounds': 0, 'favorite_bet_type': '',
                'strategy_diversity': 0.0, 'total_profit': 0.0, 'roi': 0.0,
            }
        
        amounts = np.array([bet.get('amount', 0) for bet in betting_history])
        bet_types = [bet.get('bet_type', 'unknown') for bet in betting_history]
        settled_bets = [
            bet for bet in betting_history
            if str(bet.get('outcome', '')).lower() in {'win', 'loss'}
        ]
        settled_amounts = np.array([bet.get('amount', 0) for bet in settled_bets])

        total_bets = len(betting_history)
        total_wins = sum(
            1 for bet in settled_bets if str(bet.get('outcome', '')).lower() == 'win'
        )
        total_losses = sum(
            1 for bet in settled_bets if str(bet.get('outcome', '')).lower() == 'loss'
        )
        settled_total = len(settled_bets)
        win_rate = total_wins / settled_total if settled_total > 0 else 0.0
        
        average_bet_amount = float(np.mean(amounts)) if len(amounts) > 0 else 0.0
        max_bet_amount = float(np.max(amounts)) if len(amounts) > 0 else 0.0
        min_bet_amount = float(np.min(amounts)) if len(amounts) > 0 else 0.0
        bet_variance = float(np.var(amounts)) if len(amounts) > 1 else 0.0
        
        round_ids = set(bet.get('round_id') for bet in betting_history)
        total_active_rounds = len(round_ids)
        average_bets_per_round = total_bets / total_active_rounds if total_active_rounds > 0 else 0.0
        
        unique_bet_types = len(set(bet_types))
        max_possible_types = 3
        strategy_diversity = unique_bet_types / max_possible_types if max_possible_types > 0 else 0.0
        
        bet_type_counts = {}
        for bet_type in bet_types:
            bet_type_counts[bet_type] = bet_type_counts.get(bet_type, 0) + 1
        favorite_bet_type = max(bet_type_counts, key=bet_type_counts.get) if bet_type_counts else ''
        
        payouts = np.array([bet.get('payout', 0) for bet in settled_bets])
        total_profit = float(np.sum(payouts) - np.sum(settled_amounts))
        roi = (
            total_profit / np.sum(settled_amounts) * 100
            if np.sum(settled_amounts) > 0
            else 0.0
        )
        
        return {
            'total_bets': total_bets, 'total_wins': total_wins,
            'total_losses': total_losses, 'win_rate': float(win_rate),
            'average_bet_amount': average_bet_amount, 'max_bet_amount': max_bet_amount,
            'min_bet_amount': min_bet_amount, 'bet_variance': float(bet_variance),
            'average_bets_per_round': float(average_bets_per_round),
            'total_active_rounds': total_active_rounds, 'favorite_bet_type': favorite_bet_type,
            'strategy_diversity': float(strategy_diversity), 'total_profit': total_profit,
            'roi': float(roi),
        }
    
    @staticmethod
    def batch_update_profiles(bettor_betting_data: Dict[str, List[Dict]],
                            time_window_days: Optional[int] = None) -> List[BettorProfile]:
        """Update profiles for multiple bettors efficiently."""
        updated_profiles = []
        for bettor_id, betting_history in bettor_betting_data.items():
            try:
                profile = BettorDataAggregator.update_bettor_profile_from_betting_history(
                    bettor_id=bettor_id,
                    betting_history=betting_history,
                    time_window_days=time_window_days
                )
                updated_profiles.append(profile)
            except Exception as e:
                logger.error(f"Error updating profile for bettor {bettor_id}: {str(e)}")
                continue
        logger.info(f"Updated {len(updated_profiles)} bettor profiles")
        return updated_profiles


class DataValidationService:
    """Validates and cleans betting data before ML processing."""
    
    @staticmethod
    def validate_bettor_profile(profile: BettorProfile) -> Tuple[bool, List[str]]:
        """Validate a bettor profile for ML processing."""
        errors = []
        
        if profile.total_bets < 5:
            errors.append(f"Insufficient bet history: {profile.total_bets} bets")
        
        if not np.isfinite(profile.win_rate):
            errors.append("Invalid win_rate")
        if not np.isfinite(profile.average_bet_amount):
            errors.append("Invalid average_bet_amount")
        if not np.isfinite(profile.bet_variance):
            errors.append("Invalid bet_variance")
        if not np.isfinite(profile.roi):
            errors.append("Invalid roi")
        
        if not (0 <= profile.win_rate <= 1):
            errors.append(f"Win rate out of range: {profile.win_rate}")
        if not (0 <= profile.strategy_diversity <= 1):
            errors.append(f"Strategy diversity out of range: {profile.strategy_diversity}")
        
        return len(errors) == 0, errors
    
    @staticmethod
    def get_valid_profiles_for_clustering(
        min_bets: int = 5,
        exclude_inactive_days: int = 30
    ) -> List[BettorProfile]:
        """Get profiles that are valid for clustering."""
        cutoff_date = timezone.now() - timedelta(days=exclude_inactive_days)
        
        profiles = BettorProfile.objects.filter(
            total_bets__gte=min_bets,
            last_updated__gte=cutoff_date
        )
        
        valid_profiles = []
        for profile in profiles:
            is_valid, errors = DataValidationService.validate_bettor_profile(profile)
            if is_valid:
                valid_profiles.append(profile)
            else:
                logger.warning(f"Profile {profile.bettor_id} invalid for clustering: {errors}")
        
        logger.info(f"Found {len(valid_profiles)} valid profiles for clustering")
        return valid_profiles
    
    @staticmethod
    def handle_missing_values(profiles: List[BettorProfile]) -> List[BettorProfile]:
        """Handle missing or invalid values in profiles."""
        cleaned = []
        for profile in profiles:
            if not np.isfinite(profile.bet_variance):
                profile.bet_variance = 0.0
            if not np.isfinite(profile.roi):
                profile.roi = 0.0
            if not np.isfinite(profile.average_bet_amount):
                profile.average_bet_amount = 0.0
            
            profile.win_rate = np.clip(profile.win_rate, 0, 1)
            profile.strategy_diversity = np.clip(profile.strategy_diversity, 0, 1)
            cleaned.append(profile)
        return cleaned
