// PixelCraft PC - Main JavaScript
console.log('🎮 PixelCraft PC - Sistema carregado');

// Add to cart function
function addToCart(pcId) {
    fetch('/add-to-cart', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ pc_id: pcId })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            alert('PC adicionado ao carrinho!');
            updateCartCount();
        } else {
            alert('Erro ao adicionar ao carrinho');
        }
    })
    .catch(error => {
        console.error('Erro:', error);
        alert('Erro ao adicionar ao carrinho');
    });
}

// Update cart count
function updateCartCount() {
    fetch('/api/cart-count')
    .then(response => response.json())
    .then(data => {
        const cartCount = document.querySelector('.cart-count');
        if (cartCount) {
            cartCount.textContent = data.count;
        }
    });
}

// Auto-hide alerts after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    setTimeout(() => {
        document.querySelectorAll('.alert').forEach(alert => {
            alert.style.transition = 'opacity 0.5s';
            alert.style.opacity = '0';
            setTimeout(() => alert.remove(), 500);
        });
    }, 5000);
});