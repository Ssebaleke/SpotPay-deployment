// Payment status polling to reduce wait time
function pollPaymentStatus(paymentUuid, maxAttempts = 12) {
    let attempts = 0;
    
    const checkStatus = () => {
        attempts++;
        
        fetch(`/payments/status/${paymentUuid}/`)
            .then(response => response.json())
            .then(data => {
                if (data.status === 'SUCCESS') {
                    window.location.reload();
                } else if (data.status === 'FAILED') {
                    alert('Payment failed. Please try again.');
                } else if (attempts < maxAttempts) {
                    setTimeout(checkStatus, 10000);
                } else {
                    alert('Payment taking longer than expected. Contact support if money was deducted.');
                }
            })
            .catch(error => {
                if (attempts < maxAttempts) {
                    setTimeout(checkStatus, 10000);
                }
            });
    };
    
    setTimeout(checkStatus, 15000);
}