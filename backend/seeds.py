#!/usr/bin/env python3
"""
Echoes Database Seeds - Demo Data Generation
Creates realistic demo users and sample echoes for testing and development
"""

import boto3
import json
import logging
import uuid
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Any, Optional
import random
import argparse

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EchoesSeeder:
    """Generates and inserts demo data for the Echoes application"""
    
    def __init__(self, region: str = 'us-east-1', environment: str = 'dev'):
        self.region = region
        self.environment = environment
        self.table_name = f'EchoesTable-{environment}'
        
        # Initialize AWS clients
        self.dynamodb = boto3.client('dynamodb', region_name=region)
        self.dynamodb_resource = boto3.resource('dynamodb', region_name=region)
        
        # Demo data configurations
        self.emotions = [
            'happy', 'calm', 'excited', 'peaceful', 'energetic', 
            'nostalgic', 'contemplative', 'joyful', 'serene', 'inspired'
        ]
        
        self.locations = [
            {'name': 'Central Park', 'lat': 40.7829, 'lng': -73.9654, 'type': 'park'},
            {'name': 'Santa Monica Beach', 'lat': 34.0195, 'lng': -118.4912, 'type': 'beach'},
            {'name': 'Golden Gate Bridge', 'lat': 37.8199, 'lng': -122.4783, 'type': 'landmark'},
            {'name': 'Yellowstone National Park', 'lat': 44.4280, 'lng': -110.5885, 'type': 'nature'},
            {'name': 'Times Square', 'lat': 40.7580, 'lng': -73.9855, 'type': 'urban'},
            {'name': 'Grand Canyon', 'lat': 36.1069, 'lng': -112.1129, 'type': 'nature'},
            {'name': 'Brooklyn Bridge', 'lat': 40.7061, 'lng': -73.9969, 'type': 'landmark'},
            {'name': 'Malibu Beach', 'lat': 34.0259, 'lng': -118.7798, 'type': 'beach'},
            {'name': 'Forest Hills', 'lat': 40.7128, 'lng': -73.8441, 'type': 'residential'},
            {'name': 'Downtown Coffee Shop', 'lat': 40.7484, 'lng': -73.9857, 'type': 'indoor'}
        ]
        
        self.tag_sets = [
            ['nature', 'peaceful', 'outdoors'],
            ['music', 'concert', 'energy'],
            ['family', 'home', 'cozy'],
            ['work', 'meeting', 'focus'],
            ['exercise', 'gym', 'motivation'],
            ['food', 'restaurant', 'social'],
            ['travel', 'vacation', 'adventure'],
            ['friends', 'party', 'celebration'],
            ['reading', 'quiet', 'solitude'],
            ['meditation', 'mindfulness', 'zen'],
            ['urban', 'city', 'bustling'],
            ['beach', 'waves', 'relaxation'],
            ['morning', 'sunrise', 'fresh'],
            ['evening', 'sunset', 'reflection'],
            ['rain', 'cozy', 'indoor']
        ]
        
        self.sample_transcripts = [
            "Birds chirping in the morning light, so peaceful here",
            "The sound of waves crashing against the shore",
            "Laughter and conversations at a busy cafe",
            "Wind rustling through the trees",
            "City traffic and urban energy",
            "Kids playing in the playground nearby",
            "Rain falling gently on the roof",
            "Music and cheers from a live concert",
            "Quiet moments of reflection by the lake",
            "Family dinner conversations and warmth",
            "The hum of productivity in a co-working space",
            "Ocean breeze and seagulls calling",
            "Mountain echo and crisp air",
            "Bustling market with vendors calling",
            "Peaceful library atmosphere",
            "Morning coffee shop ambiance",
            "Evening crickets and night sounds",
            "Festival music and celebration",
            "Quiet garden with fountain sounds",
            "Campfire crackling under stars"
        ]
        
        logger.info(f"Seeder initialized for {self.table_name}")
    
    def create_demo_users(self, num_users: int = 15) -> List[Dict[str, Any]]:
        """Create demo user profiles"""
        
        user_names = [
            'alex_music_lover', 'sarah_nature_girl', 'mike_city_explorer',
            'luna_dreamer', 'jake_adventure_seeker', 'maya_meditation_master',
            'noah_tech_enthusiast', 'zoe_coffee_connoisseur', 'eli_beach_walker',
            'aria_book_worm', 'leo_fitness_guru', 'ivy_travel_blogger',
            'owen_food_explorer', 'nora_photographer', 'finn_musician'
        ]
        
        users = []
        for i in range(min(num_users, len(user_names))):
            user = {
                'userId': f"user_{i+1:04d}",
                'username': user_names[i],
                'profile': {
                    'displayName': user_names[i].replace('_', ' ').title(),
                    'joined': (datetime.now() - timedelta(days=random.randint(30, 365))).isoformat(),
                    'preferences': {
                        'favorite_emotions': random.sample(self.emotions, k=3),
                        'favorite_locations': random.sample([loc['type'] for loc in self.locations], k=2)
                    }
                }
            }
            users.append(user)
        
        logger.info(f"Created {len(users)} demo user profiles")
        return users
    
    def generate_echo_for_user(self, user: Dict[str, Any], echo_index: int, 
                              total_echoes: int) -> Dict[str, Any]:
        """Generate a single echo for a user"""
        
        # Generate timestamp (distributed over the last year)
        days_ago = (echo_index / total_echoes) * 365
        timestamp = (datetime.now() - timedelta(days=days_ago)).isoformat()
        
        # Select emotion (bias towards user's favorites)
        if 'favorite_emotions' in user.get('profile', {}).get('preferences', {}):
            favorite_emotions = user['profile']['preferences']['favorite_emotions']
            emotion = random.choice(favorite_emotions + self.emotions)  # Bias towards favorites
        else:
            emotion = random.choice(self.emotions)
        
        # Select location
        location_data = random.choice(self.locations)
        
        # Add some random variation to coordinates
        lat_variation = random.uniform(-0.01, 0.01)
        lng_variation = random.uniform(-0.01, 0.01)
        
        # Select tags (related to location and emotion)
        base_tags = random.choice(self.tag_sets)
        if location_data['type'] not in base_tags:
            base_tags.append(location_data['type'])
        if emotion not in base_tags:
            base_tags.append(emotion)
        
        # Generate echo ID
        echo_id = f"echo_{uuid.uuid4().hex[:16]}"
        
        # Generate metadata
        duration = random.uniform(5.0, 120.0)  # 5 seconds to 2 minutes
        file_size = int(duration * random.uniform(8000, 15000))  # Rough estimate
        
        echo = {
            'userId': user['userId'],
            'timestamp': timestamp,
            'echoId': echo_id,
            'emotion': emotion,
            's3Url': f"s3://echoes-audio-{self.environment}/{user['userId']}/{echo_id}.webm",
            'location': {
                'lat': Decimal(str(location_data['lat'] + lat_variation)),
                'lng': Decimal(str(location_data['lng'] + lng_variation)),
                'name': location_data['name'],
                'type': location_data['type']
            },
            'tags': base_tags[:4],  # Limit to 4 tags
            'transcript': random.choice(self.sample_transcripts),
            'detectedMood': emotion,
            'createdAt': timestamp,
            'updatedAt': timestamp,
            'version': 1,
            'metadata': {
                'duration': Decimal(str(round(duration, 1))),
                'fileSize': file_size,
                'audioFormat': 'webm',
                'transcriptionConfidence': Decimal(str(round(random.uniform(0.85, 0.99), 2))),
                'qualityScore': Decimal(str(round(random.uniform(7.0, 10.0), 1)))
            }
        }
        
        # Occasionally add TTL for some echoes (for testing TTL functionality)
        if random.random() < 0.1:  # 10% of echoes
            # TTL in 1-2 years
            ttl_timestamp = datetime.now() + timedelta(days=random.randint(365, 730))
            echo['ttl'] = int(ttl_timestamp.timestamp())
        
        return echo
    
    def seed_demo_data(self, num_users: int = 15, echoes_per_user: int = 75, 
                      batch_size: int = 25) -> bool:
        """Generate and insert comprehensive demo data"""
        
        try:
            # Check if table exists
            try:
                self.dynamodb.describe_table(TableName=self.table_name)
            except self.dynamodb.exceptions.ResourceNotFoundException:
                logger.error(f"Table {self.table_name} does not exist. Run migrations first.")
                return False
            
            # Create demo users
            users = self.create_demo_users(num_users)
            
            # Generate and insert echoes
            table = self.dynamodb_resource.Table(self.table_name)
            total_echoes = num_users * echoes_per_user
            
            logger.info(f"Generating {total_echoes} demo echoes for {num_users} users...")
            
            inserted_count = 0
            
            # Process users in batches
            for user in users:
                logger.info(f"Generating echoes for user: {user['username']}")
                
                # Generate echoes for this user
                user_echoes = []
                for echo_idx in range(echoes_per_user):
                    echo = self.generate_echo_for_user(user, echo_idx, echoes_per_user)
                    user_echoes.append(echo)
                
                # Insert echoes in batches
                for i in range(0, len(user_echoes), batch_size):
                    batch = user_echoes[i:i + batch_size]
                    
                    with table.batch_writer() as batch_writer:
                        for echo in batch:
                            batch_writer.put_item(Item=echo)
                            inserted_count += 1
                    
                    if inserted_count % 100 == 0:
                        logger.info(f"Inserted {inserted_count} / {total_echoes} echoes...")
            
            logger.info(f"Successfully seeded {inserted_count} demo echoes")
            
            # Generate summary report
            self._generate_seed_report(users, inserted_count)
            
            return True
            
        except Exception as e:
            logger.error(f"Error seeding demo data: {e}")
            return False
    
    def seed_test_scenarios(self) -> bool:
        """Seed specific test scenarios for automated testing"""
        
        try:
            table = self.dynamodb_resource.Table(self.table_name)
            
            test_scenarios = [
                # User with many happy echoes
                {
                    'userId': 'test_happy_user',
                    'emotion': 'happy',
                    'count': 20,
                    'location_type': 'park'
                },
                # User with diverse emotions
                {
                    'userId': 'test_diverse_user', 
                    'emotions': ['happy', 'calm', 'excited', 'peaceful'],
                    'count': 16,  # 4 per emotion
                    'location_type': 'various'
                },
                # User with recent echoes (for time-based tests)
                {
                    'userId': 'test_recent_user',
                    'emotion': 'energetic',
                    'count': 10,
                    'time_range': 'recent'  # Last 7 days
                },
                # User with echoes from specific location
                {
                    'userId': 'test_location_user',
                    'emotion': 'peaceful',
                    'count': 15,
                    'fixed_location': {'lat': 37.7749, 'lng': -122.4194, 'name': 'Test Location'}
                }
            ]
            
            logger.info("Seeding test scenarios...")
            
            for scenario in test_scenarios:
                user_id = scenario['userId']
                
                if 'emotions' in scenario:
                    # Multiple emotions
                    emotions = scenario['emotions']
                    echoes_per_emotion = scenario['count'] // len(emotions)
                    
                    for emotion in emotions:
                        for i in range(echoes_per_emotion):
                            echo = self._create_test_echo(user_id, emotion, scenario, i)
                            table.put_item(Item=echo)
                else:
                    # Single emotion
                    emotion = scenario['emotion']
                    for i in range(scenario['count']):
                        echo = self._create_test_echo(user_id, emotion, scenario, i)
                        table.put_item(Item=echo)
                
                logger.info(f"Created test scenario for {user_id}")
            
            logger.info("Test scenarios seeded successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error seeding test scenarios: {e}")
            return False
    
    def _create_test_echo(self, user_id: str, emotion: str, scenario: Dict, index: int) -> Dict:
        """Create a test echo for specific scenarios"""
        
        # Generate timestamp based on scenario
        if scenario.get('time_range') == 'recent':
            timestamp = (datetime.now() - timedelta(hours=index * 6)).isoformat()
        else:
            timestamp = (datetime.now() - timedelta(days=index)).isoformat()
        
        # Use fixed or random location
        if 'fixed_location' in scenario:
            location = scenario['fixed_location']
        else:
            location_data = random.choice(self.locations)
            location = {
                'lat': location_data['lat'],
                'lng': location_data['lng'],
                'name': location_data['name']
            }
        
        echo_id = f"test_echo_{uuid.uuid4().hex[:12]}"
        
        return {
            'userId': user_id,
            'timestamp': timestamp,
            'echoId': echo_id,
            'emotion': emotion,
            's3Url': f"s3://echoes-audio-{self.environment}/{user_id}/{echo_id}.webm",
            'location': {
                'lat': Decimal(str(location['lat'])),
                'lng': Decimal(str(location['lng'])),
                'name': location['name']
            },
            'tags': ['test', emotion, 'automated'],
            'transcript': f"Test transcript for {emotion} echo #{index}",
            'detectedMood': emotion,
            'createdAt': timestamp,
            'updatedAt': timestamp,
            'version': 1,
            'metadata': {
                'duration': Decimal('30.0'),
                'fileSize': 500000,
                'audioFormat': 'webm',
                'transcriptionConfidence': Decimal('0.95')
            }
        }
    
    def _generate_seed_report(self, users: List[Dict], total_echoes: int):
        """Generate a summary report of seeded data"""
        
        report = {
            'seed_timestamp': datetime.now().isoformat(),
            'environment': self.environment,
            'summary': {
                'users_created': len(users),
                'echoes_created': total_echoes,
                'emotions_used': self.emotions,
                'locations_used': [loc['name'] for loc in self.locations]
            },
            'users': [
                {
                    'userId': user['userId'],
                    'username': user['username'],
                    'displayName': user['profile']['displayName']
                }
                for user in users
            ]
        }
        
        # Save report to file
        report_file = f"seed_report_{self.environment}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        try:
            with open(report_file, 'w') as f:
                json.dump(report, f, indent=2)
            logger.info(f"Seed report saved to {report_file}")
        except Exception as e:
            logger.warning(f"Could not save seed report: {e}")
    
    def clear_demo_data(self, confirm: bool = False) -> bool:
        """Clear all demo data (use with caution)"""
        
        if not confirm:
            logger.warning("Demo data clearing not confirmed. Use confirm=True to proceed.")
            return False
        
        try:
            table = self.dynamodb_resource.Table(self.table_name)
            
            # Scan and delete all items (in production, consider using batch operations)
            logger.info("Scanning for demo data to delete...")
            
            scan_kwargs = {}
            deleted_count = 0
            
            while True:
                response = table.scan(**scan_kwargs)
                
                # Delete items in batch
                with table.batch_writer() as batch:
                    for item in response['Items']:
                        batch.delete_item(
                            Key={
                                'userId': item['userId'],
                                'timestamp': item['timestamp']
                            }
                        )
                        deleted_count += 1
                
                if 'LastEvaluatedKey' not in response:
                    break
                    
                scan_kwargs['ExclusiveStartKey'] = response['LastEvaluatedKey']
                logger.info(f"Deleted {deleted_count} items so far...")
            
            logger.info(f"Cleared {deleted_count} demo data items")
            return True
            
        except Exception as e:
            logger.error(f"Error clearing demo data: {e}")
            return False


def main():
    """Main CLI interface for seeding operations"""
    
    parser = argparse.ArgumentParser(description='Echoes Database Seeder')
    parser.add_argument('--environment', default='dev', choices=['dev', 'staging', 'prod'])
    parser.add_argument('--region', default='us-east-1')
    parser.add_argument('--action', required=True, choices=[
        'seed-demo', 'seed-test', 'clear', 'report'
    ])
    parser.add_argument('--num-users', type=int, default=15, help='Number of demo users')
    parser.add_argument('--echoes-per-user', type=int, default=75, help='Echoes per user')
    parser.add_argument('--confirm', action='store_true', help='Confirm destructive operations')
    
    args = parser.parse_args()
    
    seeder = EchoesSeeder(region=args.region, environment=args.environment)
    
    success = False
    
    if args.action == 'seed-demo':
        success = seeder.seed_demo_data(args.num_users, args.echoes_per_user)
    elif args.action == 'seed-test':
        success = seeder.seed_test_scenarios()
    elif args.action == 'clear':
        success = seeder.clear_demo_data(confirm=args.confirm)
    elif args.action == 'report':
        # Generate current data report
        logger.info("Data report functionality would go here")
        success = True
    
    if success:
        logger.info(f"Action '{args.action}' completed successfully")
    else:
        logger.error(f"Action '{args.action}' failed")
    
    return success


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)