// Rafflr - Main JavaScript

// Auto-dismiss alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    const alerts = document.querySelectorAll('[data-auto-dismiss]');
    alerts.forEach(function(alert) {
        setTimeout(function() {
            alert.style.opacity = '0';
            setTimeout(function() {
                alert.remove();
            }, 300);
        }, 5000);
    });
});

// Confirm dialogs for destructive actions
document.addEventListener('DOMContentLoaded', function() {
    const confirmButtons = document.querySelectorAll('[data-confirm]');
    confirmButtons.forEach(function(button) {
        button.addEventListener('click', function(e) {
            const message = this.getAttribute('data-confirm');
            if (!confirm(message)) {
                e.preventDefault();
            }
        });
    });
});

// Dynamic price calculation for ticket purchase
function updateTotalPrice() {
    const quantityInput = document.getElementById('quantity');
    const pricePerTicket = parseFloat(document.getElementById('ticket_price')?.value || 0);
    const totalDisplay = document.getElementById('total_price');

    if (quantityInput && totalDisplay) {
        const quantity = parseInt(quantityInput.value) || 0;
        const total = (quantity * pricePerTicket).toFixed(2);
        totalDisplay.textContent = '$' + total;
    }
}

// Countdown timer for deadline
function startCountdown(elementId, deadline) {
    const element = document.getElementById(elementId);
    if (!element) return;

    const deadlineDate = new Date(deadline).getTime();

    const timer = setInterval(function() {
        const now = new Date().getTime();
        const distance = deadlineDate - now;

        if (distance < 0) {
            clearInterval(timer);
            element.textContent = 'Ended';
            return;
        }

        const days = Math.floor(distance / (1000 * 60 * 60 * 24));
        const hours = Math.floor((distance % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
        const seconds = Math.floor((distance % (1000 * 60)) / 1000);

        let text = '';
        if (days > 0) text += days + 'd ';
        if (hours > 0 || days > 0) text += hours + 'h ';
        text += minutes + 'm ' + seconds + 's';

        element.textContent = text;
    }, 1000);
}
