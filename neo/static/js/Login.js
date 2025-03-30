        // Variable to track if reCAPTCHA is verified for email/password login
        let isRecaptchaVerified = false;

        // Callback for email/password login reCAPTCHA
        function onRecaptchaSuccess(token) {
            isRecaptchaVerified = true;
        }

        // Prevent form submission if reCAPTCHA is not verified
        document.getElementById('login-form').addEventListener('submit', function(event) {
            if (!isRecaptchaVerified) {
                event.preventDefault();
                alert('Please complete the reCAPTCHA verification.');
            }
        });

        // Variable to track if reCAPTCHA is verified for Google login
        let isGoogleRecaptchaVerified = false;

        // Callback for Google login reCAPTCHA
        function onGoogleRecaptchaSuccess(token) {
            isGoogleRecaptchaVerified = true;
            // Automatically submit the form if reCAPTCHA is verified
            if (isGoogleRecaptchaVerified) {
                document.getElementById('google-login-form').submit();
            }
        }

        // Prevent Google login redirect if reCAPTCHA is not verified
        document.getElementById('google-login-button').addEventListener('click', function(event) {
            event.preventDefault();
            if (!isGoogleRecaptchaVerified) {
                alert('Please complete the reCAPTCHA verification for Google login.');
            } else {
                document.getElementById('google-login-form').submit();
            }
        });