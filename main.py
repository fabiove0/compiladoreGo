import sys

from lexer.lexer import Lexer

def main():

    if len(sys.argv) < 2:

        print("Uso: python main.py <arquivo.go>")
        return

    caminho_arquivo = sys.argv[1]

    try:

        with open(caminho_arquivo, "r", encoding="utf-8") as arquivo:

            codigo = arquivo.read()

    except FileNotFoundError:

        print("Erro: arquivo não encontrado.")
        return

    # Cria o analisador léxico
    lexer = Lexer(codigo)

    # Executa a análise
    tokens, erros = lexer.analisar()

    print("\n========== TOKENS ==========\n")

    for token in tokens:
        print(token)

    print("\n========== ERROS ==========\n")

    if erros:

        for erro in erros:
            print(erro)

    else:

        print("Nenhum erro léxico encontrado.")

    print("\n============================")


if __name__ == "__main__":
    main()