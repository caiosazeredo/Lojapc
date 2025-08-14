// PixelCraft PC - Main JavaScript

// Cart management
let cart = JSON.parse(localStorage.getItem('cart') || '[]');
updateCartCount();

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
            updateCartCount();
            showNotification('Produto adicionado ao carrinho!', 'success');
        }
    })
    .catch(error => {
        console.error('Error:', error);
        showNotification('Erro ao adicionar produto', 'error');
    });
}

function updateCartCount() {
    fetch('/cart')
        .then(response => response.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, 'text/html');
            const cartItems = doc.querySelectorAll('.cart-item').length;
            document.getElementById('cartCount').textContent = cartItems;
        });
}

function removeFromCart(pcId) {
    if (confirm('Remover este item do carrinho?')) {
        // Implement remove from cart
        location.reload();
    }
}

function updateQuantity(pcId, change) {
    // Implement quantity update
    console.log('Update quantity:', pcId, change);
}

// Search functionality
function toggleSearch() {
    const searchBar = document.getElementById('searchBar');
    searchBar.classList.toggle('active');
    if (searchBar.classList.contains('active')) {
        document.getElementById('searchInput').focus();
    }
}

function search() {
    const query = document.getElementById('searchInput').value;
    if (query.length < 2) return;
    
    fetch(`/api/search?q=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            displaySearchResults(data);
        });
}

function displaySearchResults(results) {
    const container = document.getElementById('searchResults');
    if (results.length === 0) {
        container.innerHTML = '<p>Nenhum resultado encontrado</p>';
        return;
    }
    
    let html = '<div class="search-results-list">';
    results.forEach(item => {
        html += `
            <a href="/pc/${item.slug}" class="search-result-item">
                <img src="${item.image}" alt="${item.name}">
                <div>
                    <strong>${item.name}</strong>
                    <span>R$ ${item.price.toFixed(2)}</span>
                </div>
            </a>
        `;
    });
    html += '</div>';
    container.innerHTML = html;
}

// Mobile menu
function toggleMenu() {
    const navMenu = document.getElementById('navMenu');
    navMenu.classList.toggle('active');
}

// Newsletter
function subscribeNewsletter(event) {
    event.preventDefault();
    const form = event.target;
    const email = form.querySelector('input[type="email"]').value;
    
    fetch('/api/newsletter', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ email: email })
    })
    .then(response => response.json())
    .then(data => {
        showNotification(data.message, data.success ? 'success' : 'error');
        if (data.success) {
            form.reset();
        }
    });
}

// CEP lookup (Brazilian postal code)
function buscarCEP(cep) {
    cep = cep.replace(/\D/g, '');
    if (cep.length !== 8) return;
    
    fetch(`https://viacep.com.br/ws/${cep}/json/`)
        .then(response => response.json())
        .then(data => {
            if (!data.erro) {
                document.querySelector('input[name="street"]').value = data.logradouro;
                document.querySelector('input[name="neighborhood"]').value = data.bairro;
                document.querySelector('input[name="city"]').value = data.localidade;
                document.querySelector('select[name="state"]').value = data.uf;
            }
        });
}

// Notifications
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `flash-message flash-${type}`;
    notification.innerHTML = `
        <i class="fas fa-${type === 'success' ? 'check-circle' : 'exclamation-circle'}"></i>
        ${message}
        <button onclick="this.parentElement.remove()">×</button>
    `;
    
    let container = document.querySelector('.flash-messages');
    if (!container) {
        container = document.createElement('div');
        container.className = 'flash-messages';
        document.body.appendChild(container);
    }
    
    container.appendChild(notification);
    
    setTimeout(() => {
        notification.remove();
    }, 5000);
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    // Search input listener
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        searchInput.addEventListener('input', function() {
            if (this.value.length >= 2) {
                search();
            }
        });
    }
    
    // Setup service checkbox
    const setupCheckbox = document.querySelector('input[name="setup_service"]');
    if (setupCheckbox) {
        setupCheckbox.addEventListener('change', function() {
            const setupFee = document.getElementById('setup-fee');
            const finalTotal = document.getElementById('final-total');
            
            if (this.checked) {
                setupFee.style.display = 'flex';
                // Update total with setup fee
            } else {
                setupFee.style.display = 'none';
                // Update total without setup fee
            }
        });
    }
    
    // Smooth scroll for anchor links
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function(e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) {
                target.scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }
        });
    });
    
    // Parallax effect on scroll
    window.addEventListener('scroll', function() {
        const scrolled = window.pageYOffset;
        const parallax = document.querySelector('.hero-bg');
        if (parallax) {
            parallax.style.transform = `translateY(${scrolled * 0.5}px)`;
        }
    });
});

// Prevent form submission on Enter in search
document.addEventListener('keydown', function(e) {
    if (e.key === 'Enter' && e.target.id === 'searchInput') {
        e.preventDefault();
        search();
    }
});