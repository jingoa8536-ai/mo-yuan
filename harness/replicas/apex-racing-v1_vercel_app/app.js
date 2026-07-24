// Replica App JavaScript
document.addEventListener('DOMContentLoaded', function() {
    console.log('Replica loaded for:', 'apex-racing-v1.vercel.app');

    const navLinks = document.querySelectorAll('.nav a');
    navLinks.forEach(link => {
        link.addEventListener('click', function(e) {
            const href = this.getAttribute('href');
            if (href.startsWith('#')) {
                e.preventDefault();
                const target = document.querySelector(href);
                if (target) {
                    target.scrollIntoView({ behavior: 'smooth' });
                }
            }
        });
    });

    const buttons = document.querySelectorAll('.btn');
    buttons.forEach(btn => {
        btn.addEventListener('click', function() {
            this.classList.add('btn-active');
            setTimeout(() => {
                this.classList.remove('btn-active');
            }, 200);
        });
    });
});