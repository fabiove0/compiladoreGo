"""
Maquina Virtual MaqHipo
-----------------------
Interpretador para o conjunto de instrucoes descrito na especificacao do projeto.
Formato do arquivo objeto: uma instrucao por linha, com no maximo 1 argumento.
O endereco de uma instrucao e a posicao dela no codigo, comecando em 0
(linhas em branco e comentarios nao contam).
Exemplos:
    INPP
    ALME 1
    CRCT 10
    CRCT 2.5
    CRCT "texto com espacos"
    ARMZ 0
    CRVL 0
    IMPR
    PARA
Comentarios em arquivos objeto podem comecar com # ou // (fora de strings).
 
Instrucoes dos slides: INPP PARA ALME CRCT CRVL ARMZ SOMA SUBT MULT DIVI
INVE CONJ DISJ NEGA CPME CPMA CPIG CDES CPMI CMAI DSVI DSVF LEIT IMPR
 
Instrucoes acrescentadas para o Go:
    DESM n        descarta n valores do topo
    CRVF n        carrega variavel local  (D[b + n])
    ARMF n        armazena em variavel local
    ENPR n        primeira instrucao de toda funcao com n parametros
    CHPR p        chama a funcao que comeca no endereco p
    RTPR n        retorna de uma funcao com n parametros
    MODU          resto da divisao inteira
    EBIT OUBIT XORB LIMP DESE DESD    & | ^ &^ << >>
    NBIT          ^x (nao bit a bit)
    CONV tipo     converte o topo: int, float64, rune ou string
    IMPB          imprime o topo como booleano (true/false)
    QUEB          imprime uma quebra de linha
    FMT n         Sprintf: usa n valores e o formato que esta logo abaixo
 
Valores: numeros inteiros ficam int, reais ficam float, textos ficam str.
Booleanos seguem os slides: 0 e falso, 1 e verdadeiro.
"""
import json
import math
import re
import sys
from typing import Callable, Optional
from dataclasses import dataclass
 
 
LIMITE_PILHA = 1_000_000
 
 
class ErroMaquinaVirtual(Exception):
    """Erro durante a leitura ou execucao do codigo objeto."""
 
 
@dataclass
class Instrucao:
    operacao: str
    argumento: Optional[str] = None
    linha: int = 0
 
 
def remover_comentario(linha: str) -> str:
    """Corta o comentario (# ou //) sem mexer no que esta entre aspas."""
    dentro_de_string = False
    i = 0
    while i < len(linha):
        caractere = linha[i]
        if dentro_de_string:
            if caractere == "\\":
                i += 1  # pula o caractere escapado
            elif caractere == '"':
                dentro_de_string = False
        elif caractere == '"':
            dentro_de_string = True
        elif caractere == "#" or linha.startswith("//", i):
            return linha[:i]
        i += 1
    return linha
 
 
# %[flags][largura][.precisao]verbo   (flags: - e 0)
PADRAO_FORMATO = re.compile(r"%([-0]*)(\d+)?(?:\.(\d+))?([dsvftcq%])")
 
 
def formatar_texto(formato: str, valores: list) -> str:
    """Sprintf simplificado: %d %s %v %f %t %c %q e %%."""
    usados = 0
 
    def trocar(m):
        nonlocal usados
        flags, largura, precisao, verbo = m.groups()
        if verbo == "%":
            return "%"
        if usados >= len(valores):
            return f"%!{verbo}(MISSING)"
        valor = valores[usados]
        usados += 1
 
        if verbo == "v":
            corpo = valor if isinstance(valor, str) else MaquinaVirtual._formatar_numero(valor)
        elif verbo == "d" and isinstance(valor, int):
            corpo = str(valor)
        elif verbo == "f" and isinstance(valor, float):
            casas = 6 if precisao is None else int(precisao)
            corpo = f"{valor:.{casas}f}"
        elif verbo == "s" and isinstance(valor, str):
            corpo = valor
        elif verbo == "t" and not isinstance(valor, str):
            corpo = "true" if valor != 0 else "false"
        elif verbo == "c" and isinstance(valor, int):
            corpo = chr(valor)
        elif verbo == "q" and isinstance(valor, str):
            corpo = json.dumps(valor, ensure_ascii=False)
        else:
            return f"%!{verbo}(valor incompativel)"
 
        if largura:
            tamanho = int(largura)
            if "-" in flags:
                corpo = corpo.ljust(tamanho)
            elif "0" in flags and verbo in "df":
                corpo = corpo.zfill(tamanho)
            else:
                corpo = corpo.rjust(tamanho)
        return corpo
 
    return PADRAO_FORMATO.sub(trocar, formato)
 
 
class MaquinaVirtual:
    def __init__(
        self,
        entrada: Optional[Callable[[], str]] = None,
        saida: Optional[Callable[[str], None]] = None,
    ):
        # C: codigo; D: pilha/area de dados; i: proxima instrucao; s: topo de D.
        # b: base do frame da funcao em execucao (so as funcoes usam).
        self.C: list[Instrucao] = []
        self.D: list = []
        self.i = 0
        self.s = -1
        self.b = 0
        self.executando = False
        self.entrada = entrada or input
        # A saida recebe o texto SEM quebra de linha (quem quebra e a QUEB).
        self.saida = saida or (lambda texto: print(texto, end=""))
 
    def carregar_arquivo(self, caminho: str) -> None:
        """Le um arquivo .obj e transforma cada linha em uma instrucao."""
        with open(caminho, "r", encoding="utf-8") as arquivo:
            self.carregar_texto(arquivo.read())
 
    def carregar_texto(self, texto: str) -> None:
        """Carrega codigo objeto fornecido como texto."""
        codigo = []
        for numero_linha, linha in enumerate(texto.splitlines(), start=1):
            linha = remover_comentario(linha).strip()
            if not linha:
                continue
            # So o primeiro espaco separa: o argumento pode ser uma string
            # com espacos, como CRCT "ola mundo".
            partes = linha.split(None, 1)
            operacao = partes[0].upper()
            argumento = partes[1].strip() if len(partes) == 2 else None
            codigo.append(Instrucao(operacao, argumento, numero_linha))
        self.C = codigo
        self.D = []
        self.i = 0
        self.s = -1
        self.b = 0
        self.executando = False
 
    def executar_arquivo(self, caminho: str) -> None:
        self.carregar_arquivo(caminho)
        self.executar()
 
    def executar(self) -> None:
        if not self.C:
            raise ErroMaquinaVirtual("Nenhum codigo objeto foi carregado.")
        self.D = []
        self.s = -1
        self.b = 0
        self.i = 0
        self.executando = True
        while self.executando and self.i < len(self.C):
            instrucao = self.C[self.i]
            # Avanca antes de executar; saltos podem substituir este valor.
            self.i += 1
            try:
                self._executar_instrucao(instrucao)
            except ErroMaquinaVirtual as erro:
                raise ErroMaquinaVirtual(
                    f"Linha {instrucao.linha} ({instrucao.operacao}): {erro}"
                ) from None
            except (IndexError, TypeError, ValueError, OverflowError):
                raise ErroMaquinaVirtual(
                    f"Linha {instrucao.linha} ({instrucao.operacao}): "
                    "valores ou enderecos invalidos para esta instrucao."
                ) from None
        if self.executando:
            raise ErroMaquinaVirtual(
                "O programa terminou sem executar PARA."
            )
 
    # ------------------------------------------------------------
    # Instrucoes
    # ------------------------------------------------------------
 
    def _executar_instrucao(self, ins: Instrucao) -> None:
        op = ins.operacao
 
        # Controle do programa
        if op == "INPP":
            self._exigir_argumento_ausente(ins)
            self.D = []
            self.s = -1
            self.b = 0
 
        elif op == "PARA":
            self._exigir_argumento_ausente(ins)
            self.executando = False
 
        # Constantes e acesso a memoria
        elif op == "CRCT":
            if ins.argumento is None:
                raise ErroMaquinaVirtual("CRCT exige uma constante.")
            if ins.argumento.startswith('"'):
                try:
                    constante = json.loads(ins.argumento)
                except ValueError:
                    raise ErroMaquinaVirtual("String invalida em CRCT.")
            else:
                try:
                    constante = self._numero(ins.argumento)
                except ValueError:
                    raise ErroMaquinaVirtual(
                        f"Constante invalida: {ins.argumento}."
                    )
            self._empilhar(constante)
 
        elif op == "CRVL":
            endereco = self._argumento_inteiro(ins)
            if endereco < 0 or endereco >= len(self.D):
                raise ErroMaquinaVirtual(
                    f"Endereco de memoria invalido: {endereco}."
                )
            self._empilhar(self.D[endereco])
 
        elif op == "ARMZ":
            endereco = self._argumento_inteiro(ins)
            valor = self._desempilhar()
            self._armazenar_em(endereco, valor)
 
        # Variaveis locais: o endereco e relativo a base b do frame
        elif op == "CRVF":
            endereco = self.b + self._argumento_inteiro(ins)
            if endereco < 0 or endereco >= len(self.D):
                raise ErroMaquinaVirtual(
                    f"Endereco de memoria invalido: {endereco}."
                )
            self._empilhar(self.D[endereco])
 
        elif op == "ARMF":
            endereco = self.b + self._argumento_inteiro(ins)
            valor = self._desempilhar()
            self._armazenar_em(endereco, valor)
 
        elif op == "ALME":
            quantidade = self._argumento_inteiro(ins)
            if quantidade < 0:
                raise ErroMaquinaVirtual("ALME nao pode reservar tamanho negativo.")
            for _ in range(quantidade):
                self._empilhar(0.0)
 
        elif op == "DESM":
            quantidade = self._argumento_inteiro(ins)
            if quantidade < 0 or quantidade > len(self.D):
                raise ErroMaquinaVirtual("DESM com quantidade invalida.")
            for _ in range(quantidade):
                self._desempilhar()
 
        # Operacoes aritmeticas (SOMA tambem concatena strings)
        elif op in ("SOMA", "SUBT", "MULT", "DIVI", "MODU"):
            self._exigir_argumento_ausente(ins)
            esquerda, direita = self._dois_operandos()
            if op == "SOMA":
                resultado = esquerda + direita
            elif op == "SUBT":
                resultado = esquerda - direita
            elif op == "MULT":
                resultado = esquerda * direita
            elif op == "DIVI":
                if direita == 0:
                    raise ErroMaquinaVirtual("Divisao por zero.")
                if isinstance(esquerda, int) and isinstance(direita, int):
                    # Em Go a divisao inteira trunca para zero (// arredonda para baixo).
                    resultado = abs(esquerda) // abs(direita)
                    if (esquerda < 0) != (direita < 0):
                        resultado = -resultado
                else:
                    resultado = esquerda / direita
            else:
                if direita == 0:
                    raise ErroMaquinaVirtual("Divisao por zero.")
                # Em Go o resto tem o sinal do dividendo.
                resultado = abs(esquerda) % abs(direita)
                if esquerda < 0:
                    resultado = -resultado
            self._empilhar(self._limitar_64(resultado))
 
        elif op == "INVE":
            self._exigir_argumento_ausente(ins)
            self._empilhar(self._limitar_64(-self._desempilhar()))
 
        # Operacoes bit a bit (so inteiros)
        elif op in ("EBIT", "OUBIT", "XORB", "LIMP", "DESE", "DESD"):
            self._exigir_argumento_ausente(ins)
            esquerda, direita = self._dois_operandos()
            if op == "EBIT":
                resultado = esquerda & direita
            elif op == "OUBIT":
                resultado = esquerda | direita
            elif op == "XORB":
                resultado = esquerda ^ direita
            elif op == "LIMP":
                resultado = esquerda & ~direita
            else:
                if direita < 0:
                    raise ErroMaquinaVirtual("Deslocamento negativo.")
                direita = min(direita, 64)
                resultado = esquerda << direita if op == "DESE" else esquerda >> direita
            self._empilhar(self._limitar_64(resultado))
 
        elif op == "NBIT":
            self._exigir_argumento_ausente(ins)
            self._empilhar(~self._desempilhar())
 
        # Operacoes logicas: zero e falso; qualquer valor diferente de zero e verdadeiro.
        elif op in ("CONJ", "DISJ"):
            self._exigir_argumento_ausente(ins)
            esquerda, direita = self._dois_operandos()
            a = esquerda != 0
            b = direita != 0
            resultado = (a and b) if op == "CONJ" else (a or b)
            self._empilhar(1.0 if resultado else 0.0)
 
        elif op == "NEGA":
            self._exigir_argumento_ausente(ins)
            valor = self._desempilhar()
            self._empilhar(0.0 if valor != 0 else 1.0)
 
        # Comparacoes
        elif op in ("CPME", "CPMA", "CPIG", "CDES", "CPMI", "CMAI"):
            self._exigir_argumento_ausente(ins)
            esquerda, direita = self._dois_operandos()
            comparacoes = {
                "CPME": esquerda < direita,
                "CPMA": esquerda > direita,
                "CPIG": esquerda == direita,
                "CDES": esquerda != direita,
                "CPMI": esquerda <= direita,
                "CMAI": esquerda >= direita,
            }
            self._empilhar(1.0 if comparacoes[op] else 0.0)
 
        # Desvios. Os destinos sao indices de instrucao, comecando em zero.
        elif op == "DSVI":
            destino = self._argumento_inteiro(ins)
            self._validar_destino(destino)
            self.i = destino
 
        elif op == "DSVF":
            destino = self._argumento_inteiro(ins)
            condicao = self._desempilhar()
            if condicao == 0:
                self._validar_destino(destino)
                self.i = destino
 
        # Funcoes. O chamador reserva os valores de retorno (ALME r), empilha
        # os argumentos e faz CHPR. Layout do frame, a partir de b:
        #   b-r .. b-1     valores de retorno (ARMF com numero negativo)
        #   b .. b+n-1     parametros
        #   b+n, b+n+1     endereco de retorno e b antigo
        #   b+n+2 ..       variaveis locais
        elif op == "CHPR":
            destino = self._argumento_inteiro(ins)
            self._validar_destino(destino)
            if len(self.D) > LIMITE_PILHA:
                raise ErroMaquinaVirtual("Estouro de pilha (recursao infinita?).")
            self._empilhar(self.i)
            self._empilhar(self.b)
            self.i = destino
 
        elif op == "ENPR":
            parametros = self._argumento_inteiro(ins)
            self.b = len(self.D) - 2 - parametros
 
        elif op == "RTPR":
            parametros = self._argumento_inteiro(ins)
            retorno = self.D[self.b + parametros]
            base_antiga = self.D[self.b + parametros + 1]
            # Corta parametros, dados de controle e locais; os valores de
            # retorno ficam no topo para o chamador.
            del self.D[self.b:]
            self.s = len(self.D) - 1
            self.b = base_antiga
            self.i = retorno
 
        # Conversao de tipo
        elif op == "CONV":
            if ins.argumento is None:
                raise ErroMaquinaVirtual("CONV exige um tipo.")
            valor = self._desempilhar()
            if ins.argumento == "float64":
                valor = float(valor)
            elif ins.argumento in ("int", "rune"):
                valor = self._limitar_64(int(valor))
            elif ins.argumento == "string" and isinstance(valor, int):
                valor = chr(valor)
            self._empilhar(valor)
 
        # Entrada e saida
        elif op == "LEIT":
            self._exigir_argumento_ausente(ins)
            try:
                valor = self._numero(self.entrada().strip())
            except (ValueError, EOFError):
                raise ErroMaquinaVirtual("A entrada precisa ser um numero.")
            self._empilhar(valor)
 
        elif op == "IMPR":
            self._exigir_argumento_ausente(ins)
            valor = self._desempilhar()
            if isinstance(valor, str):
                self.saida(valor)
            else:
                self.saida(self._formatar_numero(valor))
 
        elif op == "IMPB":
            self._exigir_argumento_ausente(ins)
            self.saida("true" if self._desempilhar() != 0 else "false")
 
        elif op == "QUEB":
            self._exigir_argumento_ausente(ins)
            self.saida("\n")
 
        elif op == "FMT":
            quantidade = self._argumento_inteiro(ins)
            valores = [self._desempilhar() for _ in range(quantidade)]
            valores.reverse()
            formato = self._desempilhar()
            self._empilhar(formatar_texto(formato, valores))
 
        else:
            raise ErroMaquinaVirtual(f"Instrucao desconhecida: {op}.")
 
    # ------------------------------------------------------------
    # Auxiliares
    # ------------------------------------------------------------
 
    def _empilhar(self, valor) -> None:
        self.D.append(valor)
        self.s = len(self.D) - 1
 
    def _desempilhar(self):
        if not self.D:
            raise ErroMaquinaVirtual("Pilha vazia.")
        valor = self.D.pop()
        self.s = len(self.D) - 1
        return valor
 
    def _dois_operandos(self):
        """Tira os dois valores do topo: (antecessor, topo)."""
        direita = self._desempilhar()
        esquerda = self._desempilhar()
        return esquerda, direita
 
    def _armazenar_em(self, endereco: int, valor) -> None:
        if endereco < 0 or endereco >= len(self.D):
            raise ErroMaquinaVirtual(
                f"Endereco de memoria invalido: {endereco}."
            )
        self.D[endereco] = valor
 
    def _argumento_inteiro(self, ins: Instrucao) -> int:
        if ins.argumento is None:
            raise ErroMaquinaVirtual(f"{ins.operacao} exige um argumento inteiro.")
        try:
            return int(ins.argumento)
        except ValueError:
            raise ErroMaquinaVirtual(
                f"{ins.operacao} exige um argumento inteiro, recebeu {ins.argumento}."
            )
 
    @staticmethod
    def _exigir_argumento_ausente(ins: Instrucao) -> None:
        if ins.argumento is not None:
            raise ErroMaquinaVirtual(f"{ins.operacao} nao aceita argumento.")
 
    @staticmethod
    def _numero(texto: str):
        """'10' vira int e '2.5' vira float (ValueError se nao for numero)."""
        try:
            return int(texto)
        except ValueError:
            return float(texto)
 
    @staticmethod
    def _limitar_64(valor):
        """int de Go tem 64 bits e da a volta quando estoura."""
        if isinstance(valor, int):
            return (valor + 2 ** 63) % 2 ** 64 - 2 ** 63
        return valor
 
    def _validar_destino(self, destino: int) -> None:
        if destino < 0 or destino >= len(self.C):
            raise ErroMaquinaVirtual(
                f"Destino de salto fora do codigo: {destino}."
            )
 
    @staticmethod
    def _formatar_numero(valor) -> str:
        if isinstance(valor, int):
            return str(valor)
        if math.isfinite(valor) and valor.is_integer():
            return str(int(valor))
        return str(valor)
 
 
if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Uso: python maqhipo/maquina.py arquivo.obj")
        raise SystemExit(1)
 
    maquina = MaquinaVirtual()
    try:
        maquina.executar_arquivo(sys.argv[1])
    except ErroMaquinaVirtual as erro:
        print(f"Erro na maquina virtual: {erro}")
        raise SystemExit(1)
 