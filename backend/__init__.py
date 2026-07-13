"""backend/ — U1 共有基盤の実装（LC-02 AssignmentEngine / LC-03 Repository /
LC-04 Serializer / LC-05 LogEmitter）。

層の逆流禁止（U1-NFR-15）: 本パッケージは schema/ のみを import し、上位ユニット
（participant/admin/scripts）へは依存しない。
"""
