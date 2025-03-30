// Signup form submission
document.getElementById('signupForm').addEventListener('submit', async function(event) {
    event.preventDefault();  // Prevent form submission
    
    const password = document.getElementById('password').value;
    const confirmPassword = document.getElementById('confirm-password').value;
    const modal = document.getElementById('otpModal');

    // Password validation
    if (password !== confirmPassword) {
        alert('Passwords do not match');
        return;
    }

    try {
        const formData = new FormData(this);
        const response = await fetch('/signup/', {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                'X-Requested-With': 'XMLHttpRequest'  // Add this to indicate AJAX request
            }
        });

        const data = await response.json();
        console.log('Server response:', data);  // Debug log

        if (response.ok && data.status === 'success') {
            // Show OTP modal
            modal.style.display = 'block';
            startTimer();
            
            // Clear any previous error messages
            document.getElementById('errorMessage').style.display = 'none';
            
            // Clear OTP input
            document.getElementById('otp').value = '';
        } else {
            alert(data.error || 'An error occurred');
        }
    } catch (error) {
        console.error('Error:', error);
        alert('An error occurred. Please try again.');
    }
});
async function verifyOTP() {
    const otp = document.getElementById('otp').value;
    const email = document.getElementById('email').value;
    const errorMessage = document.getElementById('errorMessage');

    console.log('Verifying OTP for email:', email);

    try {
        // Correct request format: Send JSON data instead of FormData
        const response = await fetch('/verify-otp/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',  //Important: Set correct Content-Type
                'X-CSRFToken': document.querySelector('[name=csrfmiddlewaretoken]').value,
                'X-Requested-With': 'XMLHttpRequest'
            },
            body: JSON.stringify({  //Convert data to JSON format
                email: email,
                otp: otp
            })
        });

        // Check if the response is actually JSON
        const contentType = response.headers.get("content-type");
        if (!contentType || !contentType.includes("application/json")) {
            throw new Error("Server did not return JSON");
        }

        const data = await response.json();
        console.log('Verification response:', data);

        if (response.ok && data.status === 'success') {
            errorMessage.style.display = 'block';
            errorMessage.style.color = 'green';
            errorMessage.textContent = 'Registration successful! Redirecting...';

            setTimeout(() => {
                window.location.href = '/login/';
            }, 1500);
        } else {
            errorMessage.style.display = 'block';
            errorMessage.style.color = 'red';
            errorMessage.textContent = data.error || 'Invalid OTP';
        }
    } catch (error) {
        console.error('Verification error:', error);
        errorMessage.style.display = 'block';
        errorMessage.style.color = 'red';
        errorMessage.textContent = 'An error occurred. Please try again.';
    }
}


// Initialize timer variable
let timeLeft = 300;
let timerId = null;

// Timer function
function startTimer() {
    timeLeft = 300;
    const timerDisplay = document.getElementById('timer');
    
    // Clear any existing timer
    if (timerId) clearInterval(timerId);
    
    timerId = setInterval(() => {
        if (timeLeft <= 0) {
            clearInterval(timerId);
            timerDisplay.textContent = 'OTP expired';
            return;
        }
        
        timerDisplay.textContent = `Time remaining: ${timeLeft}s`;
        timeLeft--;
    }, 1000);
}