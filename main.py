import sys

from parser.grammar import gramatica
from parser.parser import criar_parser, ErroSintatico
from lexer.lexer import Lexer
from ast_nodes.builder import construir_ast, ErroAST
from semantico.semantico import analisar_semantica
from gerador_codigo.gerador import gerar_codigo
from gerador_codigo.instrucoes import salvar_programa
from maqhipo.maquina import MaquinaVirtual, ErroMaquinaVirtual


def falhar(*mensagens):
    for m in mensagens:
        print(m)
    sys.exit(1)


def compilar(caminho, destino):
    try:
        with open(caminho, "r", encoding="utf-8") as arquivo:
            codigo = arquivo.read()
    except FileNotFoundError:
        falhar("Erro: arquivo não encontrado.")

    if not gramatica.validar():
        falhar("A gramática possui erros.")

    parser = criar_parser(gramatica)
    tokens, erros_lexicos = Lexer(codigo).analisar()

    if erros_lexicos:
        falhar("Erros léxicos encontrados:",
               *[f" - {e}" for e in erros_lexicos])

    try:
        ast = construir_ast(parser.analisar(tokens))
    except (ErroSintatico, ErroAST) as erro:
        falhar(erro)

    erros = analisar_semantica(ast)
    if erros:
        falhar("Erros semânticos encontrados:",
               *[f" - {e}" for e in erros])

    instrucoes = gerar_codigo(ast)
    salvar_programa(instrucoes, destino, com_enderecos=False)
    print(f"Código objeto gerado: {destino} ({len(instrucoes)} instruções)")


def main():
    args = sys.argv[1:]
    so_compilar = "--compilar" in args
    args = [a for a in args if a != "--compilar"]

    if not args:
        falhar("Uso: python main.py <arquivo.go> [arquivo.obj] [--compilar]")

    destino = args[1] if len(args) > 1 else "programa.obj"
    compilar(args[0], destino)

    if so_compilar:
        return

    print("--- Execução ---")
    try:
        MaquinaVirtual().executar_arquivo(destino)
    except ErroMaquinaVirtual as erro:
        falhar(f"Erro na máquina virtual: {erro}")


if __name__ == "__main__":
    main()