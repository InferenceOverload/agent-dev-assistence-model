"""Tests for Rally story extender."""

from src.agents.rally_extender import extend_story_with_context


class TestRallyExtender:
    """Tests for Rally story extension functions."""
    
    def test_extend_with_full_context(self):
        """Test extending a story with full repository context."""
        # Setup Rally context
        rally_context = {
            'story': {
                'id': '123',
                'title': 'Add OAuth authentication',
                'description': 'Implement OAuth 2.0 flow',
                'acceptance_criteria': '<ul><li>OAuth works</li></ul>',
                'state': 'In-Progress'
            },
            'feature': {
                'id': '789',
                'title': 'Authentication System'
            }
        }
        
        # Setup repo context
        repo_context = {
            'files': [
                'src/api/routes.py',
                'src/api/middleware.py',
                'src/auth/oauth.py',
                'src/auth/jwt.py',
                'tests/test_auth.py',
                'tests/test_api.py'
            ],
            'components': ['api', 'auth', 'database'],
            'frameworks': ['FastAPI', 'SQLAlchemy']
        }
        
        # Extend the story
        extension = extend_story_with_context(
            rally_context,
            repo_context,
            "implementation tasks for OAuth authentication"
        )
        
        # Verify extension structure
        assert extension['story_id'] == '123'
        assert extension['story_title'] == 'Add OAuth authentication'
        assert extension['context_available'] is True
        assert 'created_at' in extension
        
        # Verify tasks were created
        assert len(extension['tasks']) > 0
        
        # Should have auth-related tasks
        task_titles = [t['title'] for t in extension['tasks']]
        assert any('auth' in title.lower() for title in task_titles)
        
        # Should have appropriate tags
        all_tags = []
        for task in extension['tasks']:
            all_tags.extend(task.get('tags', []))
        assert 'auth' in all_tags or 'authentication' in all_tags
    
    def test_extend_without_context(self):
        """Test extending a story without repository context."""
        # Setup Rally context
        rally_context = {
            'story': {
                'id': '456',
                'title': 'Add payment processing',
                'description': 'Integrate Stripe payments'
            },
            'feature': {}
        }
        
        # Empty repo context
        repo_context = {}
        
        # Extend the story
        extension = extend_story_with_context(
            rally_context,
            repo_context,
            "implementation tasks for payment integration"
        )
        
        # Verify extension
        assert extension['story_id'] == '456'
        assert extension['context_available'] is False
        assert 'note' in extension
        assert 'repository context' in extension['note']
        
        # Should have generic tasks
        assert len(extension['tasks']) > 0
        
        # Check for standard task types
        task_titles = [t['title'] for t in extension['tasks']]
        assert any('research' in title.lower() for title in task_titles)
        assert any('implementation' in title.lower() for title in task_titles)
        assert any('test' in title.lower() for title in task_titles)
        assert any('documentation' in title.lower() for title in task_titles)
    
    def test_extend_api_tasks(self):
        """Test generating API-specific tasks."""
        rally_context = {
            'story': {
                'id': '111',
                'title': 'Create REST API endpoints',
                'description': 'Add CRUD operations'
            }
        }
        
        repo_context = {
            'files': [
                'src/api/routes/users.py',
                'src/api/routes/products.py',
                'src/api/middleware/auth.py',
                'tests/api/test_users.py'
            ],
            'components': ['api', 'database'],
            'frameworks': ['FastAPI']
        }
        
        extension = extend_story_with_context(
            rally_context,
            repo_context,
            "create API endpoints with full CRUD operations"
        )
        
        # Should have API-related tasks
        task_titles = [t['title'] for t in extension['tasks']]
        assert any('API' in title for title in task_titles)
        
        # Should reference API files in descriptions
        all_descriptions = ' '.join(t['description'] for t in extension['tasks'])
        assert 'api' in all_descriptions.lower() or 'endpoint' in all_descriptions.lower()
    
    def test_extend_testing_tasks(self):
        """Test generating testing-specific tasks."""
        rally_context = {
            'story': {
                'id': '222',
                'title': 'Improve test coverage',
                'description': 'Add unit and integration tests'
            }
        }
        
        repo_context = {
            'files': [
                'src/services/user_service.py',
                'src/services/product_service.py',
                'tests/unit/test_users.py',
                'tests/integration/test_api.py'
            ],
            'components': ['services', 'api'],
            'frameworks': ['pytest']
        }
        
        extension = extend_story_with_context(
            rally_context,
            repo_context,
            "add comprehensive test coverage"
        )
        
        # Should have testing tasks
        task_titles = [t['title'] for t in extension['tasks']]
        assert any('test' in title.lower() for title in task_titles)
        
        # Should have both unit and integration test tasks
        assert any('unit' in title.lower() for title in task_titles)
        assert any('integration' in title.lower() for title in task_titles)
    
    def test_extend_database_tasks(self):
        """Test generating database-specific tasks."""
        rally_context = {
            'story': {
                'id': '333',
                'title': 'Update database schema',
                'description': 'Add new tables for features'
            }
        }
        
        repo_context = {
            'files': [
                'src/models/user.py',
                'src/models/product.py',
                'src/database/migrations/001_initial.py',
                'src/database/connection.py'
            ],
            'components': ['database', 'models'],
            'frameworks': ['SQLAlchemy']
        }
        
        extension = extend_story_with_context(
            rally_context,
            repo_context,
            "update database models and create migrations"
        )
        
        # Should have database tasks
        task_titles = [t['title'] for t in extension['tasks']]
        assert any('database' in title.lower() or 'model' in title.lower() for title in task_titles)
        assert any('migration' in title.lower() for title in task_titles)
        
        # Should reference model files
        all_descriptions = ' '.join(t['description'] for t in extension['tasks'])
        assert 'models' in all_descriptions.lower() or 'schema' in all_descriptions.lower()
    
    def test_task_estimates(self):
        """Test that tasks have reasonable estimates."""
        rally_context = {
            'story': {
                'id': '444',
                'title': 'Complex feature',
                'description': 'Multi-component feature'
            }
        }
        
        repo_context = {
            'files': ['src/main.py'],
            'components': ['api', 'auth', 'database'],
            'frameworks': ['FastAPI']
        }
        
        extension = extend_story_with_context(
            rally_context,
            repo_context,
            "implement authentication and API endpoints"
        )
        
        # All tasks should have estimates
        for task in extension['tasks']:
            assert 'estimate' in task
            assert isinstance(task['estimate'], (int, float))
            assert 0 < task['estimate'] <= 8  # Reasonable range
    
    def test_task_tags(self):
        """Test that tasks have appropriate tags."""
        rally_context = {
            'story': {
                'id': '555',
                'title': 'Feature with tags',
                'description': 'Testing tag generation'
            }
        }
        
        repo_context = {
            'files': ['src/api/routes.py', 'tests/test_api.py'],
            'components': ['api'],
            'frameworks': []
        }
        
        extension = extend_story_with_context(
            rally_context,
            repo_context,
            "create API with tests"
        )
        
        # All tasks should have tags
        for task in extension['tasks']:
            assert 'tags' in task
            assert isinstance(task['tags'], list)
            assert len(task['tags']) > 0