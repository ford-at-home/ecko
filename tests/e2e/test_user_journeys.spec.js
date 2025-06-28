/**
 * End-to-end tests for Echoes audio time machine
 * Tests complete user journeys through the web interface
 */

import { test, expect } from '@playwright/test';

// Test data
const testUser = {
  email: 'testuser@example.com',
  password: 'TestPassword123!',
  userId: 'test-user-123'
};

const testEcho = {
  emotion: 'joyful',
  location: 'Central Park, NYC',
  tags: ['nature', 'peaceful']
};

test.describe('Echoes User Journeys', () => {
  
  test.beforeEach(async ({ page }) => {
    // Set up browser permissions for microphone and location
    await page.context().grantPermissions(['microphone', 'geolocation']);
    
    // Mock geolocation
    await page.addInitScript(() => {
      navigator.geolocation.getCurrentPosition = function(success) {
        success({
          coords: {
            latitude: 40.7829,
            longitude: -73.9654,
            accuracy: 10
          }
        });
      };
    });
    
    // Navigate to app
    await page.goto('http://localhost:3000');
  });

  test.describe('First-time User Journey', () => {
    
    test('new user can sign up and create first echo', async ({ page }) => {
      // Step 1: Navigate to sign up
      await page.click('[data-testid="sign-up-button"]');
      await expect(page).toHaveURL(/\/signup/);
      
      // Step 2: Complete sign up form
      await page.fill('[data-testid="email-input"]', testUser.email);
      await page.fill('[data-testid="password-input"]', testUser.password);
      await page.fill('[data-testid="confirm-password-input"]', testUser.password);
      await page.click('[data-testid="submit-signup"]');
      
      // Step 3: Verify email confirmation (mock)
      await expect(page.locator('[data-testid="email-verification-sent"]')).toBeVisible();
      
      // Step 4: Mock email verification click
      await page.click('[data-testid="verify-email-mock"]');
      await expect(page).toHaveURL(/\/welcome/);
      
      // Step 5: Complete welcome flow
      await page.click('[data-testid="get-started-button"]');
      await expect(page).toHaveURL(/\/home/);
      
      // Step 6: See welcome message for new users
      await expect(page.locator('[data-testid="welcome-new-user"]')).toBeVisible();
      await expect(page.locator('text=Create your first Echo')).toBeVisible();
      
      // Step 7: Navigate to record screen
      await page.click('[data-testid="create-first-echo"]');
      await expect(page).toHaveURL(/\/record/);
      
      // Step 8: Select emotion
      await page.click(`[data-testid="emotion-${testEcho.emotion}"]`);
      await expect(page.locator(`[data-testid="emotion-${testEcho.emotion}"]`)).toHaveClass(/selected/);
      
      // Step 9: Grant microphone permission and start recording
      await page.click('[data-testid="start-recording"]');
      
      // Wait for recording state
      await expect(page.locator('[data-testid="recording-status"]')).toBeVisible();
      await expect(page.locator('text=Recording...')).toBeVisible();
      
      // Step 10: Record for a few seconds
      await page.waitForTimeout(3000);
      
      // Step 11: Stop recording
      await page.click('[data-testid="stop-recording"]');
      
      // Step 12: Review recording
      await expect(page.locator('[data-testid="recording-preview"]')).toBeVisible();
      await expect(page.locator('[data-testid="play-preview"]')).toBeVisible();
      
      // Step 13: Save echo
      await page.click('[data-testid="save-echo"]');
      
      // Step 14: Wait for save confirmation
      await expect(page.locator('[data-testid="echo-saved-success"]')).toBeVisible();
      
      // Step 15: Navigate back to home
      await expect(page).toHaveURL(/\/home/);
      
      // Step 16: Verify first echo appears in suggestions
      await expect(page.locator('[data-testid="emotion-input"]')).toBeVisible();
      await page.fill('[data-testid="emotion-input"]', testEcho.emotion);
      await page.click('[data-testid="find-echo"]');
      
      // Step 17: Verify echo is found and can be played
      await expect(page.locator('[data-testid="echo-found"]')).toBeVisible();
      await expect(page.locator('[data-testid="echo-preview"]')).toBeVisible();
    });

    test('new user can complete onboarding tutorial', async ({ page }) => {
      // Start onboarding
      await page.click('[data-testid="start-tutorial"]');
      
      // Tutorial step 1: Home screen explanation
      await expect(page.locator('[data-testid="tutorial-step-1"]')).toBeVisible();
      await expect(page.locator('text=Find echoes by emotion')).toBeVisible();
      await page.click('[data-testid="tutorial-next"]');
      
      // Tutorial step 2: Record screen explanation
      await expect(page.locator('[data-testid="tutorial-step-2"]')).toBeVisible();
      await expect(page.locator('text=Capture moments with emotion')).toBeVisible();
      await page.click('[data-testid="tutorial-next"]');
      
      // Tutorial step 3: Echo list explanation
      await expect(page.locator('[data-testid="tutorial-step-3"]')).toBeVisible();
      await expect(page.locator('text=Browse your memory collection')).toBeVisible();
      await page.click('[data-testid="tutorial-next"]');
      
      // Tutorial completion
      await expect(page.locator('[data-testid="tutorial-complete"]')).toBeVisible();
      await page.click('[data-testid="tutorial-finish"]');
      
      // Verify tutorial completion is saved
      await page.reload();
      await expect(page.locator('[data-testid="start-tutorial"]')).not.toBeVisible();
    });
  });

  test.describe('Returning User Journey', () => {
    
    test.beforeEach(async ({ page }) => {
      // Mock existing user authentication
      await page.addInitScript(() => {
        localStorage.setItem('echoes_auth', JSON.stringify({
          accessToken: 'mock-access-token',
          userId: 'test-user-123',
          email: 'testuser@example.com'
        }));
      });
    });

    test('returning user can find and play existing echoes', async ({ page }) => {
      // Page should show home screen for authenticated user
      await expect(page).toHaveURL(/\/home/);
      await expect(page.locator('[data-testid="emotion-input"]')).toBeVisible();
      
      // Search for echoes by emotion
      await page.fill('[data-testid="emotion-input"]', 'peaceful');
      await page.click('[data-testid="find-echo"]');
      
      // Wait for search results
      await expect(page.locator('[data-testid="searching-echoes"]')).toBeVisible();
      
      // Verify echo found (mock data)
      await expect(page.locator('[data-testid="echo-found"]')).toBeVisible();
      await expect(page.locator('[data-testid="echo-emotion"]')).toContainText('peaceful');
      
      // Play echo preview
      await page.click('[data-testid="play-echo-preview"]');
      await expect(page.locator('[data-testid="audio-player"]')).toBeVisible();
      
      // View full echo details
      await page.click('[data-testid="view-echo-details"]');
      await expect(page).toHaveURL(/\/playback/);
      
      // Verify full echo playback interface
      await expect(page.locator('[data-testid="echo-playback"]')).toBeVisible();
      await expect(page.locator('[data-testid="echo-metadata"]')).toBeVisible();
      await expect(page.locator('[data-testid="echo-location"]')).toBeVisible();
      await expect(page.locator('[data-testid="echo-timestamp"]')).toBeVisible();
    });

    test('user can browse echo collection', async ({ page }) => {
      // Navigate to echo list
      await page.click('[data-testid="echo-list-nav"]');
      await expect(page).toHaveURL(/\/echoes/);
      
      // Verify echo list interface
      await expect(page.locator('[data-testid="echo-list"]')).toBeVisible();
      await expect(page.locator('[data-testid="filter-controls"]')).toBeVisible();
      
      // Test emotion filter
      await page.selectOption('[data-testid="emotion-filter"]', 'joy');
      await expect(page.locator('[data-testid="echo-item"]')).toBeVisible();
      
      // Test date range filter
      await page.click('[data-testid="date-filter"]');
      await page.click('[data-testid="last-month"]');
      
      // Test search functionality
      await page.fill('[data-testid="search-echoes"]', 'sunset');
      await page.press('[data-testid="search-echoes"]', 'Enter');
      
      // Verify search results
      await expect(page.locator('[data-testid="search-results"]')).toBeVisible();
      
      // Test echo interaction
      await page.click('[data-testid="echo-item"]:first-child');
      await expect(page).toHaveURL(/\/playback/);
    });

    test('user can create new echo with rich metadata', async ({ page }) => {
      // Navigate to record screen
      await page.click('[data-testid="record-new-echo"]');
      await expect(page).toHaveURL(/\/record/);
      
      // Select custom emotion
      await page.click('[data-testid="emotion-other"]');
      await page.fill('[data-testid="custom-emotion-input"]', 'contemplative');
      
      // Add tags
      await page.fill('[data-testid="tags-input"]', 'morning, coffee, reflection');
      
      // Verify location capture
      await expect(page.locator('[data-testid="current-location"]')).toBeVisible();
      
      // Start recording
      await page.click('[data-testid="start-recording"]');
      await page.waitForTimeout(5000); // Record for 5 seconds
      await page.click('[data-testid="stop-recording"]');
      
      // Review and edit metadata
      await page.fill('[data-testid="echo-description"]', 'Morning reflection over coffee');
      
      // Save echo
      await page.click('[data-testid="save-echo"]');
      
      // Verify success and navigation
      await expect(page.locator('[data-testid="echo-saved-success"]')).toBeVisible();
      await expect(page).toHaveURL(/\/home/);
      
      // Verify new echo appears in search
      await page.fill('[data-testid="emotion-input"]', 'contemplative');
      await page.click('[data-testid="find-echo"]');
      await expect(page.locator('[data-testid="echo-found"]')).toBeVisible();
    });
  });

  test.describe('Echo Playback Journey', () => {
    
    test('user can experience full echo playback', async ({ page }) => {
      // Navigate to a specific echo (mock URL)
      await page.goto('http://localhost:3000/playback/test-echo-123');
      
      // Verify full-screen nostalgia experience
      await expect(page.locator('[data-testid="echo-playback-fullscreen"]')).toBeVisible();
      await expect(page.locator('[data-testid="echo-emotion-display"]')).toBeVisible();
      
      // Test audio controls
      await page.click('[data-testid="play-echo"]');
      await expect(page.locator('[data-testid="audio-playing"]')).toBeVisible();
      
      // Test pause/resume
      await page.click('[data-testid="pause-echo"]');
      await expect(page.locator('[data-testid="audio-paused"]')).toBeVisible();
      
      // Test seek functionality
      await page.click('[data-testid="audio-progress-bar"]');
      
      // View metadata
      await page.click('[data-testid="show-metadata"]');
      await expect(page.locator('[data-testid="echo-timestamp"]')).toBeVisible();
      await expect(page.locator('[data-testid="echo-location"]')).toBeVisible();
      await expect(page.locator('[data-testid="echo-tags"]')).toBeVisible();
      
      // Test sharing functionality
      await page.click('[data-testid="share-echo"]');
      await expect(page.locator('[data-testid="share-modal"]')).toBeVisible();
      
      // Copy share link
      await page.click('[data-testid="copy-share-link"]');
      await expect(page.locator('[data-testid="link-copied"]')).toBeVisible();
      
      // Test delete functionality
      await page.click('[data-testid="delete-echo"]');
      await expect(page.locator('[data-testid="delete-confirmation"]')).toBeVisible();
      await page.click('[data-testid="cancel-delete"]');
    });

    test('user can edit echo metadata from playback', async ({ page }) => {
      await page.goto('http://localhost:3000/playback/test-echo-123');
      
      // Enter edit mode
      await page.click('[data-testid="edit-echo"]');
      await expect(page.locator('[data-testid="edit-mode"]')).toBeVisible();
      
      // Edit tags
      await page.fill('[data-testid="edit-tags"]', 'updated, peaceful, nature');
      
      // Edit description
      await page.fill('[data-testid="edit-description"]', 'Updated description of this peaceful moment');
      
      // Save changes
      await page.click('[data-testid="save-edits"]');
      
      // Verify changes saved
      await expect(page.locator('[data-testid="edits-saved"]')).toBeVisible();
      await expect(page.locator('text=Updated description')).toBeVisible();
    });
  });

  test.describe('Search and Discovery Journey', () => {
    
    test('user can discover echoes through various methods', async ({ page }) => {
      await page.goto('http://localhost:3000/home');
      
      // Test emotion-based search
      await page.fill('[data-testid="emotion-input"]', 'nostalgic');
      await page.click('[data-testid="find-echo"]');
      await expect(page.locator('[data-testid="echo-found"]')).toBeVisible();
      
      // Test "surprise me" functionality
      await page.click('[data-testid="surprise-me"]');
      await expect(page.locator('[data-testid="random-echo"]')).toBeVisible();
      
      // Test location-based discovery
      await page.click('[data-testid="echoes-near-me"]');
      await expect(page.locator('[data-testid="location-echoes"]')).toBeVisible();
      
      // Test time-based discovery
      await page.click('[data-testid="echoes-from-this-day"]');
      await expect(page.locator('[data-testid="historical-echoes"]')).toBeVisible();
      
      // Test mood-based recommendations
      await page.click('[data-testid="current-mood-match"]');
      await expect(page.locator('[data-testid="mood-recommendations"]')).toBeVisible();
    });

    test('user can use advanced search filters', async ({ page }) => {
      await page.goto('http://localhost:3000/search');
      
      // Open advanced filters
      await page.click('[data-testid="advanced-filters"]');
      
      // Set date range
      await page.fill('[data-testid="date-from"]', '2024-01-01');
      await page.fill('[data-testid="date-to"]', '2024-12-31');
      
      // Set location radius
      await page.fill('[data-testid="location-radius"]', '10');
      
      // Select multiple emotions
      await page.check('[data-testid="emotion-joy"]');
      await page.check('[data-testid="emotion-peaceful"]');
      
      // Set duration filter
      await page.selectOption('[data-testid="duration-filter"]', '10-30');
      
      // Apply filters
      await page.click('[data-testid="apply-filters"]');
      
      // Verify filtered results
      await expect(page.locator('[data-testid="filtered-results"]')).toBeVisible();
      await expect(page.locator('[data-testid="results-count"]')).toBeVisible();
    });
  });

  test.describe('Mobile Responsive Journey', () => {
    
    test('mobile user can complete full echo creation flow', async ({ page }) => {
      // Set mobile viewport
      await page.setViewportSize({ width: 375, height: 667 });
      
      await page.goto('http://localhost:3000');
      
      // Test mobile navigation
      await page.click('[data-testid="mobile-menu"]');
      await expect(page.locator('[data-testid="mobile-nav-menu"]')).toBeVisible();
      
      // Navigate to record
      await page.click('[data-testid="mobile-nav-record"]');
      await expect(page).toHaveURL(/\/record/);
      
      // Test mobile emotion selection (swipe/scroll)
      await page.locator('[data-testid="emotion-carousel"]').scrollIntoViewIfNeeded();
      await page.click('[data-testid="emotion-joy"]');
      
      // Test mobile recording interface
      await page.click('[data-testid="mobile-record-button"]');
      await expect(page.locator('[data-testid="mobile-recording-ui"]')).toBeVisible();
      
      // Test mobile audio visualization
      await expect(page.locator('[data-testid="mobile-waveform"]')).toBeVisible();
      
      // Complete recording
      await page.waitForTimeout(3000);
      await page.click('[data-testid="mobile-stop-button"]');
      
      // Test mobile playback controls
      await page.click('[data-testid="mobile-play-preview"]');
      
      // Save echo with mobile interface
      await page.click('[data-testid="mobile-save-echo"]');
      
      // Verify mobile success state
      await expect(page.locator('[data-testid="mobile-success"]')).toBeVisible();
    });
  });

  test.describe('Accessibility Journey', () => {
    
    test('user can navigate app with keyboard only', async ({ page }) => {
      await page.goto('http://localhost:3000');
      
      // Test keyboard navigation through main interface
      await page.keyboard.press('Tab');
      await expect(page.locator('[data-testid="emotion-input"]')).toBeFocused();
      
      await page.keyboard.press('Tab');
      await expect(page.locator('[data-testid="find-echo"]')).toBeFocused();
      
      // Test keyboard shortcuts
      await page.keyboard.press('Alt+r'); // Record shortcut
      await expect(page).toHaveURL(/\/record/);
      
      await page.keyboard.press('Alt+h'); // Home shortcut
      await expect(page).toHaveURL(/\/home/);
      
      // Test form navigation with keyboard
      await page.goto('http://localhost:3000/record');
      await page.keyboard.press('Tab');
      await page.keyboard.press('Enter'); // Select first emotion
      
      await page.keyboard.press('Tab');
      await page.keyboard.press('Space'); // Start recording
      
      await page.waitForTimeout(2000);
      await page.keyboard.press('Space'); // Stop recording
    });

    test('screen reader user can complete echo creation', async ({ page }) => {
      await page.goto('http://localhost:3000/record');
      
      // Verify ARIA labels and roles
      await expect(page.locator('[role="group"][aria-label="Emotion selection"]')).toBeVisible();
      await expect(page.locator('[role="button"][aria-label="Start recording echo"]')).toBeVisible();
      
      // Verify live region announcements
      await page.click('[data-testid="emotion-joy"]');
      await expect(page.locator('[aria-live="polite"]')).toContainText('Joy emotion selected');
      
      // Test recording announcements
      await page.click('[data-testid="start-recording"]');
      await expect(page.locator('[aria-live="assertive"]')).toContainText('Recording started');
      
      await page.waitForTimeout(2000);
      await page.click('[data-testid="stop-recording"]');
      await expect(page.locator('[aria-live="assertive"]')).toContainText('Recording stopped');
      
      // Verify form labels and descriptions
      await expect(page.locator('[aria-describedby="recording-help"]')).toBeVisible();
    });
  });

  test.describe('Error Handling Journey', () => {
    
    test('user can recover from network failures', async ({ page }) => {
      await page.goto('http://localhost:3000');
      
      // Simulate network failure
      await page.route('**/api/**', route => route.abort());
      
      // Attempt search
      await page.fill('[data-testid="emotion-input"]', 'joy');
      await page.click('[data-testid="find-echo"]');
      
      // Verify error message
      await expect(page.locator('[data-testid="network-error"]')).toBeVisible();
      await expect(page.locator('[data-testid="retry-button"]')).toBeVisible();
      
      // Restore network and retry
      await page.unroute('**/api/**');
      await page.click('[data-testid="retry-button"]');
      
      // Verify recovery
      await expect(page.locator('[data-testid="echo-found"]')).toBeVisible();
    });

    test('user can handle recording permission denials', async ({ page }) => {
      // Deny microphone permission
      await page.context().clearPermissions();
      
      await page.goto('http://localhost:3000/record');
      
      // Select emotion and try to record
      await page.click('[data-testid="emotion-joy"]');
      await page.click('[data-testid="start-recording"]');
      
      // Verify permission error handling
      await expect(page.locator('[data-testid="permission-error"]')).toBeVisible();
      await expect(page.locator('[data-testid="grant-permission"]')).toBeVisible();
      
      // Test alternative recording methods
      await page.click('[data-testid="upload-audio-file"]');
      await expect(page.locator('[data-testid="file-upload"]')).toBeVisible();
    });
  });
});