import type { CapacitorConfig } from '@capacitor/cli';

const config: CapacitorConfig = {
  appId: 'com.companyai.app',
  appName: 'CompanyAI',
  webDir: 'dist',

  // Sunucudaki web arayüzünü yükle (desktop viewer mantığı)
  server: {
    url: 'http://192.168.0.12',
    cleartext: true,               // HTTP izni (Android 9+)
    errorPath: 'error.html',       // Sunucu ulaşılamazsa
  },

  // Android ayarları
  android: {
    allowMixedContent: true,       // HTTP + HTTPS karışık içerik
    backgroundColor: '#0f1117',    // Splash arka plan
    overrideUserAgent: 'CompanyAI-Mobile/2.6.0',
  },

  // iOS ayarları
  ios: {
    backgroundColor: '#0f1117',
    overrideUserAgent: 'CompanyAI-Mobile/2.6.0',
    preferredContentMode: 'mobile',
    scheme: 'CompanyAI',
  },

  plugins: {
    SplashScreen: {
      launchShowDuration: 2000,
      launchAutoHide: true,
      backgroundColor: '#0f1117',
      showSpinner: true,
      spinnerColor: '#6366f1',
      androidScaleType: 'CENTER_CROP',
    },
    StatusBar: {
      style: 'DARK',
      backgroundColor: '#0f1117',
    },
  },
};

export default config;
