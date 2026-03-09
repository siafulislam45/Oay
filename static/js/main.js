document.addEventListener('DOMContentLoaded', () => {
    
    // --- bKash Style Balance Animation ---
    const balanceWrapper = document.getElementById('balanceBtn');
    const balanceText = document.getElementById('balanceText');
    let balanceTimeout;

    if (balanceWrapper && balanceText) {
        balanceWrapper.addEventListener('click', () => {
            // ১. এনিমেশন শুরু (Blur সরানো)
            if (balanceText.classList.contains('blur-sm')) {
                balanceText.classList.remove('blur-sm'); // ঘোলা ভাব সরানো
                balanceText.classList.add('scale-110');  // একটু বড় করা (Zoom)
                
                // ২. টাইমার সেট করা (৩ সেকেন্ড পর আবার হাইড হবে)
                clearTimeout(balanceTimeout);
                balanceTimeout = setTimeout(() => {
                    balanceText.classList.add('blur-sm'); // আবার ঘোলা করা
                    balanceText.classList.remove('scale-110'); // সাইজ ছোট করা
                }, 3000); // 3000ms = 3 seconds
            }
        });
    }

    // --- Flash Message Auto Hide ---
    // নোটিফিকেশন মেসেজ ৫ সেকেন্ড পর গায়েব হয়ে যাবে
    const flashMessages = document.querySelectorAll('.flash-msg');
    if (flashMessages.length > 0) {
        setTimeout(() => {
            flashMessages.forEach(msg => {
                msg.style.transition = "opacity 0.5s ease";
                msg.style.opacity = "0";
                setTimeout(() => msg.remove(), 500);
            });
        }, 4000);
    }
});
