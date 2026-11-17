class ErroLexico:

    def __init__(self, mensagem, caractere, linha, coluna):

        self.mensagem = mensagem
        self.caractere = caractere
        self.linha = linha
        self.coluna = coluna

    def __str__(self):

        return (
            f"Erro léxico na linha {self.linha}, "
            f"coluna {self.coluna}: "
            f"{self.mensagem} "
            f"Caractere: '{self.caractere}'"
        )