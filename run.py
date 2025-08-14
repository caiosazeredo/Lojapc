#!/usr/bin/env python3
"""
Script para iniciar o servidor PixelCraft PC
"""

import os
import sys

# Adiciona o diretório ao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Importa e roda a aplicação
from app import app

if __name__ == '__main__':
    print("=" * 60)
    print("PixelCraft PC - Servidor Iniciado")
    print("=" * 60)
    print("\n🚀 Acesse: http://localhost:5000")
    print("👨‍💼 Admin: http://localhost:5000/admin")
    print("   Usuário: admin")
    print("   Senha: admin123")
    print("\nPressione CTRL+C para parar o servidor")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000)
