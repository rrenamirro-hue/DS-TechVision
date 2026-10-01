# HTTPS Android — diagnóstico 0.4.1

## Certificado presente el 30-09-2026

- Archivo de servidor: `%LOCALAPPDATA%\DataSystems\DS_TechVision\certs\server-cert.pem`.
- Subject: `CN=192.168.100.122,O=DataSystems`.
- Issuer: `CN=DS TechVision Local CA,O=DataSystems`.
- SAN: `IP:192.168.100.122`, `DNS:localhost`, `IP:127.0.0.1`.
- Validez: `2026-09-30 12:33:59 UTC` a `2029-01-02 12:38:59 UTC`.
- Huella SHA-256 del servidor: `1A084BAC866460C43247B91DC14139ACC7EA89103FE33FDD11EC9EFA4BF651CF`.
- CA local: `%LOCALAPPDATA%\DataSystems\DS_TechVision\certs\ca-cert.cer`, autofirmada; huella SHA-256 `74F9B46D750BE4FA14B149B0603142DFF81D26A9FCCF9EBC9EDCAABB7C00584F`.
- El emisor del certificado de servidor coincide con el subject de la CA. El nombre `localhost` está cubierto por SAN, por lo que no se observó un error de nombre en los archivos locales.

No se pudo inspeccionar el certificado efectivamente presentado por `https://localhost:8522` en Android: no hubo dispositivo conectado en esta sesión y `adb` no está en el PATH. La advertencia roja observada es **compatible con CA local no confiada** o con un certificado servido distinto/caducado, pero no se puede atribuir una causa única sin ver el código de error de Chrome Android.

## Verificación en el Android

1. Confirmar fecha y hora del teléfono y de la PC.
2. Conectar USB, habilitar depuración y comprobar que `adb devices` muestre el equipo como `device` (no `unauthorized`). Ejecutar `adb reverse tcp:8522 tcp:8522` y `adb reverse --list`.
3. Copiar **solo** `ca-cert.cer` al teléfono. Comparar su huella SHA-256 con la indicada arriba antes de instalar. Nunca copiar `ca-key.pem` ni `server-key.pem`.
4. En Android, instalarlo como **certificado de CA** desde Ajustes → Seguridad y privacidad → Más ajustes de seguridad → Cifrado y credenciales → Instalar certificado. Los nombres varían según fabricante. Verificar que figure entre credenciales de usuario. [Ayuda oficial de Pixel sobre certificados](https://support.google.com/pixelphone/answer/2844832).
5. Reiniciar Chrome y abrir `https://localhost:8522` sin aceptar una excepción de seguridad. Verificar candado/estado de conexión, emisor, SAN y huella del certificado servido. Anotar el código de error exacto si sigue la pantalla roja.
6. Si aparece un certificado anterior, regenerar la CA solo como operación consciente: cada CA nueva exige reinstalar confianza en Android. El script actual reutiliza certificados mientras el archivo de servidor tenga la IP privada y más de 30 días de vigencia.

ADB reverse **no** desactiva TLS ni instala confianza. Para una APK o WebView en vez de Chrome/PWA, Android moderno puede requerir configuración explícita de anclas de confianza; esto es distinto de confiar una CA en Chrome. Ver [Network Security Configuration de Android](https://developer.android.com/privacy-and-security/security-config).

Estado: **pendiente de prueba física en Android**. No se deshabilitó TLS ni la verificación de certificados.
