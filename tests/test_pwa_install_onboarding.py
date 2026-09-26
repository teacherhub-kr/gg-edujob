import unittest
from pathlib import Path


class PwaInstallOnboardingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = Path("app.js").read_text(encoding="utf-8")
        cls.css = Path("app.css").read_text(encoding="utf-8")
        cls.index = Path("index.html").read_text(encoding="utf-8")
        cls.manifest = Path("manifest.webmanifest").read_text(encoding="utf-8")
        cls.icon = Path("edujob-icon.svg").read_text(encoding="utf-8")

    def test_install_prompt_is_platform_aware(self):
        self.assertIn("beforeinstallprompt", self.app)
        self.assertIn("appinstalled", self.app)
        self.assertIn("isIOSDevice", self.app)
        self.assertIn("isStandaloneApp", self.app)
        self.assertIn("iosNeedsInstall", self.app)

    def test_ios_never_uses_android_chrome_intent_without_guard(self):
        self.assertIn("package=com.android.chrome", self.app)
        self.assertIn("if(isIOSDevice())", self.app)
        self.assertIn("iPhone에서는 홈 화면에 추가한 에듀잡 앱에서 알림을 켜주세요.", self.app)

    def test_home_screen_install_card_is_visible_only_when_not_installed(self):
        self.assertIn("shouldShowInstallCard", self.app)
        self.assertIn("!isStandaloneApp()", self.app)
        self.assertIn("에듀잡을 홈 화면에 추가하세요", self.app)
        self.assertIn("에듀잡 앱 설치", self.app)
        self.assertIn("data-install-dismiss", self.app)

    def test_android_in_app_browser_hands_install_off_to_chrome(self):
        self.assertIn("isAndroidInAppBrowser", self.app)
        self.assertIn("KAKAOTALK", self.app)
        self.assertIn("Chrome에서 설치하기", self.app)
        self.assertIn("data-install-chrome", self.app)
        self.assertIn("chromeInstallIntentUrl", self.app)\n        self.assertIn("installHandoffRequested", self.app)\n        self.assertIn("?install=1", self.app)

    def test_service_worker_registration_is_not_alert_config_dependent(self):
        self.assertIn("navigator.serviceWorker.register('./sw.js'", self.app)

    def test_manifest_remains_standalone(self):
        self.assertIn('"display": "standalone"', self.manifest)

    def test_cache_busts_install_onboarding_assets(self):
        self.assertIn("app.css?v=20260923pwa1", self.index)
        self.assertIn("app.js?v=20260926pwa3", self.index)

    def test_install_card_styles_exist(self):
        self.assertIn(".install-card{", self.css)
        self.assertIn(".ios-install-steps{", self.css)
        self.assertIn(".install-primary-btn{", self.css)

    def test_new_brand_logo_drives_home_screen_icon(self):
        self.assertIn("승인된 신형 수도권에듀잡 로고", self.icon)
        self.assertIn("data:image/png;base64,", self.icon)
        self.assertIn("edujob-icon.svg?v=20260923new1", self.manifest)
        self.assertIn('rel="apple-touch-icon"', self.index)
        self.assertIn("assets/logo-mark.png?v=20260923new1", self.index)


if __name__ == "__main__":
    unittest.main()
