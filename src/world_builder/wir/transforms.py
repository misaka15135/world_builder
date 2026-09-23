from __future__ import annotations

from typing import Iterable, Sequence, Tuple

Vector3 = Tuple[float, float, float]
Matrix3 = Tuple[Vector3, Vector3, Vector3]

WIR_TO_GLTF: Matrix3 = ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0))
WIR_TO_MINECRAFT: Matrix3 = WIR_TO_GLTF
WIR_TO_UNITY: Matrix3 = ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, 1.0, 0.0))
WIR_TO_IFC: Matrix3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))


def apply(matrix: Matrix3, vector: Sequence[float]) -> Vector3:
    if len(vector) != 3:
        raise ValueError("a coordinate must contain exactly three values")
    return tuple(sum(row[index] * float(vector[index]) for index in range(3)) for row in matrix)  # type: ignore[return-value]


def transpose(matrix: Matrix3) -> Matrix3:
    return tuple(tuple(matrix[row][column] for row in range(3)) for column in range(3))  # type: ignore[return-value]


def determinant(matrix: Matrix3) -> float:
    a, b, c = matrix
    return (
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    )


def round_trip(matrix: Matrix3, vector: Sequence[float]) -> Vector3:
    return apply(transpose(matrix), apply(matrix, vector))


def requires_reflection_handling(matrix: Matrix3) -> bool:
    return determinant(matrix) < 0.0
