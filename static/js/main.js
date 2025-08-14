// PixelCraft PC - JavaScript Principal

// Inicialização
document.addEventListener('DOMContentLoaded', function() {
    console.log('🎮 PixelCraft PC - Sistema carregado');
    
    // Atualiza contador do carrinho
    updateCartCount();
    
    // Setup dos filtros
    setupFilters();
    
    // Setup da busca
    setupSearch();
    
    // Animações
    setupAnimations();
});

// Carrinho
let cart = JSON.parse(sessionStorage.getItem('cart') || '[]');

function addToCart(pcId) {
    console.log('Adicionando ao carrinho:', pcId);
    
    // Simula request para servidor
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
            showNotification('PC adicionado ao carrinho! 🛒', 'success');
        } else {
            showNotification('Erro ao adicionar ao carrinho', 'error');
        }
    })
    .catch(error => {
        console.error('Erro:', error);
        // Fallback para modo offline
        addToCartOffline(pcId);
    });
}

function addToCartOffline(pcId) {
    // Adiciona ao carrinho local como fallback
    const item = {
        id: pcId,
        name: 'PC PixelCraft',
        price: 2999.90,
        quantity: 1,
        timestamp: Date.now()
    };
    
    cart.push(item);
    sessionStorage.setItem('cart', JSON.stringify(cart));
    updateCartCount();
    showNotification('PC adicionado ao carrinho (offline) 🛒', 'success');
}

function updateCartCount() {
    const cartCountElement = document.getElementById('cartCount');
    if (cartCountElement) {
        const count = cart.length;
        cartCountElement.textContent = count;
        cartCountElement.style.display = count > 0 ? 'flex' : 'none';
    }
}

function removeFromCart(pcId) {
    if (confirm('Remover este PC do carrinho?')) {
        cart = cart.filter(item => item.id !== pcId);
        sessionStorage.setItem('cart', JSON.stringify(cart));
        updateCartCount();
        showNotification('PC removido do carrinho', 'info');
        location.reload();
    }
}

// Busca
function toggleSearch() {
    const searchBar = document.getElementById('searchBar');
    if (searchBar) {
        searchBar.classList.toggle('active');
        if (searchBar.classList.contains('active')) {
            const searchInput = document.getElementById('searchInput');
            if (searchInput) {
                searchInput.focus();
            }
        }
    }
}

function setupSearch() {
    const searchInput = document.getElementById('searchInput');
    if (searchInput) {
        let searchTimeout;
        searchInput.addEventListener('input', function() {
            clearTimeout(searchTimeout);
            if (this.value.length >= 2) {
                searchTimeout = setTimeout(() => {
                    performSearch(this.value);
                }, 300);
            } else {
                clearSearchResults();
            }
        });
        
        // Enter para buscar
        searchInput.addEventListener('keydown', function(e) {
            if (e.key === 'Enter') {
                e.preventDefault();
                if (this.value.length >= 2) {
                    performSearch(this.value);
                }
            }
        });
    }
}

function performSearch(query) {
    console.log('Buscando por:', query);
    
    fetch(`/api/search?q=${encodeURIComponent(query)}`)
        .then(response => response.json())
        .then(data => {
            displaySearchResults(data);
        })
        .catch(error => {
            console.error('Erro na busca:', error);
            displaySearchResults([]);
        });
}

function displaySearchResults(results) {
    const container = document.getElementById('searchResults');
    if (!container) return;
    
    if (results.length === 0) {
        container.innerHTML = '<div style="padding: 20px; text-align: center; color: #9CA3AF;">Nenhum resultado encontrado</div>';
        return;
    }
    
    let html = '<div class="search-results-list" style="max-height: 400px; overflow-y: auto;">';
    results.forEach(item => {
        html += `
            <a href="/pc/${item.slug}" class="search-result-item" style="display: flex; padding: 15px; border-bottom: 1px solid rgba(255,255,255,0.1); text-decoration: none; color: white;">
                <img src="${item.image || '/static/img/placeholder.svg'}" alt="${item.name}" style="width: 60px; height: 60px; border-radius: 8px; object-fit: cover;">
                <div style="margin-left: 15px;">
                    <div style="font-weight: 600; margin-bottom: 4px;">${item.name}</div>
                    <div style="color: #8B5CF6; font-weight: 700;">R$ ${formatPrice(item.price)}</div>
                </div>
            </a>
        `;
    });
    html += '</div>';
    container.innerHTML = html;
}

function clearSearchResults() {
    const container = document.getElementById('searchResults');
    if (container) {
        container.innerHTML = '';
    }
}

// Filtros
function setupFilters() {
    // Filtros de performance
    const performanceFilters = document.querySelectorAll('input[name="performance"]');
    performanceFilters.forEach(filter => {
        filter.addEventListener('change', applyFilters);
    });
}

function applyFilters() {
    const priceMin = document.getElementById('priceMin')?.value;
    const priceMax = document.getElementById('priceMax')?.value;
    
    let url = new URL(window.location.href);
    
    if (priceMin) {
        url.searchParams.set('price_min', priceMin);
    } else {
        url.searchParams.delete('price_min');
    }
    
    if (priceMax) {
        url.searchParams.set('price_max', priceMax);
    } else {
        url.searchParams.delete('price_max');
    }
    
    // Performance filters
    const selectedPerformance = Array.from(document.querySelectorAll('input[name="performance"]:checked'))
        .map(cb => cb.value);
    
    if (selectedPerformance.length > 0) {
        url.searchParams.set('performance', selectedPerformance.join(','));
    } else {
        url.searchParams.delete('performance');
    }
    
    window.location.href = url.toString();
}

function sortProducts(sort) {
    let url = new URL(window.location.href);
    url.searchParams.set('sort', sort);
    window.location.href = url.toString();
}

// Menu mobile
function toggleMenu() {
    const navMenu = document.getElementById('navMenu');
    if (navMenu) {
        navMenu.classList.toggle('active');
    }
}

// Notificações
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.innerHTML = `
        <div style="
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${type === 'success' ? '#10B981' : type === 'error' ? '#EF4444' : '#8B5CF6'};
            color: white;
            padding: 15px 25px;
            border-radius: 10px;
            box-shadow: 0 10px 30px rgba(0,0,0,0.3);
            z-index: 10000;
            display: flex;
            align-items: center;
            gap: 10px;
            animation: slideInRight 0.3s ease;
        ">
            <span>${message}</span>
            <button onclick="this.parentElement.parentElement.remove()" style="
                background: none;
                border: none;
                color: white;
                font-size: 18px;
                cursor: pointer;
                padding: 0 5px;
            ">×</button>
        </div>
    `;
    
    document.body.appendChild(notification);
    
    // Remove automaticamente após 4 segundos
    setTimeout(() => {
        if (notification.parentNode) {
            notification.remove();
        }
    }, 4000);
}

// Animações
function setupAnimations() {
    // Lazy loading para imagens
    if ('IntersectionObserver' in window) {
        const imageObserver = new IntersectionObserver((entries, observer) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const img = entry.target;
                    if (img.dataset.src) {
                        img.src = img.dataset.src;
                        img.classList.remove('lazy');
                        observer.unobserve(img);
                    }
                }
            });
        });

        document.querySelectorAll('img[data-src]').forEach(img => {
            imageObserver.observe(img);
        });
    }
    
    // Scroll smooth
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
}

// Utilities
function formatPrice(price) {
    return new Intl.NumberFormat('pt-BR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
    }).format(price);
}

// CEP (para checkout)
function buscarCEP(cep) {
    cep = cep.replace(/\D/g, '');
    if (cep.length !== 8) return;
    
    fetch(`https://viacep.com.br/ws/${cep}/json/`)
        .then(response => response.json())
        .then(data => {
            if (!data.erro) {
                const streetInput = document.querySelector('input[name="street"]');
                const neighborhoodInput = document.querySelector('input[name="neighborhood"]');
                const cityInput = document.querySelector('input[name="city"]');
                const stateSelect = document.querySelector('select[name="state"]');
                
                if (streetInput) streetInput.value = data.logradouro;
                if (neighborhoodInput) neighborhoodInput.value = data.bairro;
                if (cityInput) cityInput.value = data.localidade;
                if (stateSelect) stateSelect.value = data.uf;
                
                showNotification('CEP encontrado! ✅', 'success');
            } else {
                showNotification('CEP não encontrado', 'error');
            }
        })
        .catch(error => {
            console.error('Erro ao buscar CEP:', error);
            showNotification('Erro ao buscar CEP', 'error');
        });
}

// Newsletter
function subscribeNewsletter(event) {
    event.preventDefault();
    const form = event.target;
    const email = form.querySelector('input[type="email"]').value;
    
    if (!email) {
        showNotification('Digite um e-mail válido', 'error');
        return;
    }
    
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
    })
    .catch(error => {
        console.error('Erro:', error);
        showNotification('E-mail cadastrado com sucesso! (modo offline)', 'success');
        form.reset();
    });
}

// CSS para animações
const style = document.createElement('style');
style.textContent = `
    @keyframes slideInRight {
        from {
            transform: translateX(100%);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    .lazy {
        opacity: 0.5;
        transition: opacity 0.3s;
    }
`;
document.head.appendChild(style);
