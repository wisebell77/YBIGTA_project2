"""대규모 패널용 고정효과 추정기 (numpy bincount 기반)

46.7M행 × 다중 FE는 pyfixest로 메모리·시간이 감당되지 않아 직접 구현한다.
반드시 validate_against_pyfixest() 로 Phase 3A 결과와 대조 검증한 뒤 사용할 것.

지원: 단일 회귀변수 D, 다중 FE(반복 demeaning), CRV1 1-way / 2-way(CGM) cluster SE
소표본 보정은 pyfixest 기본값(ssc: adj=True, fixef_k='none', cluster_adj=True)을 따른다.
"""

# ── release bootstrap ─────────────────────────────────────────────────
# repository root 기준 경로만 사용한다. 절대경로 하드코딩 금지.
import sys as _sys
from pathlib import Path as _Path
_sys.path.insert(0, str(_Path(__file__).resolve().parents[1]))
from common.paths import PROJECT_ROOT  # noqa: E402
# ──────────────────────────────────────────────────────────────────────

import numpy as np


def _codes(*arrays):
    """여러 배열을 결합해 0..G-1 정수 코드로 변환"""
    if len(arrays) == 1:
        return np.unique(arrays[0], return_inverse=True)[1].astype(np.int64)
    key = np.zeros(len(arrays[0]), dtype=np.int64)
    for a in arrays:
        c = np.unique(a, return_inverse=True)[1].astype(np.int64)
        key = key * (c.max() + 1) + c
    return np.unique(key, return_inverse=True)[1].astype(np.int64)


def _sweep(mat, groups, cnts):
    """한 번의 alternating projection 스윕 (제자리)"""
    for g, cnt in zip(groups, cnts):
        for j in range(mat.shape[1]):
            m = np.bincount(g, weights=mat[:, j]) / cnt
            mat[:, j] -= m[g]


def _demean(mat, groups, tol=1e-10, maxiter=3000):
    """mat: (n,k) float64. groups: 코드배열 리스트.

    단일 FE는 1회로 정확. 다중 FE는 alternating projection + Irons-Tuck 가속.
    가속 없이는 이 데이터에서 5,000 스윕이 필요해 대규모 패널에 쓸 수 없다
    (검증 스크립트로 확인함).
    """
    if len(groups) == 1:
        g = groups[0]
        cnt = np.bincount(g).astype(np.float64)
        for j in range(mat.shape[1]):
            m = np.bincount(g, weights=mat[:, j]) / cnt
            mat[:, j] -= m[g]
        return mat, 1

    cnts = [np.bincount(g).astype(np.float64) for g in groups]
    prev = np.empty_like(mat)
    x1 = np.empty_like(mat)
    it = 0
    while it < maxiter:
        prev[:] = mat
        _sweep(mat, groups, cnts); it += 1
        x1[:] = mat
        _sweep(mat, groups, cnts); it += 1

        d1 = x1 - prev          # Δ1
        d2 = mat - x1           # Δ2
        dd = d2 - d1            # Δ²
        den = float((dd * dd).sum())
        if den > 0:
            step = float((d2 * dd).sum()) / den
            if np.isfinite(step) and abs(step) < 1e6:
                mat -= step * d2        # Irons-Tuck 외삽
        if float(np.abs(d2).max()) < tol:
            break
    return mat, it


def _meat(xe, cl):
    """cluster별 sum(x*e) 의 제곱합"""
    s = np.bincount(cl, weights=xe)
    return float(s @ s)


def drop_singletons(groups, n):
    """FE 그룹 크기가 1인 관측치를 반복 제거. beta에는 영향이 없으나
    pyfixest와 동일한 N·자유도를 얻으려면 필요하다."""
    keep = np.ones(n, dtype=bool)
    while True:
        removed = False
        for g in groups:
            cnt = np.bincount(g[keep], minlength=int(g.max()) + 1)
            bad = keep & (cnt[g] < 2)
            if bad.any():
                keep &= ~bad
                removed = True
        if not removed:
            return keep


def _nested_in(g, cl):
    """FE g가 cluster cl 안에 완전히 중첩되는가 (각 FE 수준이 한 cluster에만 속하는가)"""
    order = np.argsort(g, kind="stable")
    gs, cs = g[order], cl[order]
    bnd = np.r_[True, gs[1:] != gs[:-1]]
    first = np.repeat(cs[bnd], np.diff(np.r_[np.flatnonzero(bnd), len(gs)]))
    return bool((cs == first).all())


def feols1(y, D, fe_groups, cluster=None, cluster2=None, name="D",
           drop_singleton=True):
    """단일 회귀변수 FE 회귀.
    y, D: 1D float array / fe_groups: 코드배열 리스트
    cluster, cluster2: 코드배열 (2-way 는 CGM)

    자유도 보정은 pyfixest 기본값과 일치시킨다:
      * singleton 제거
      * cluster에 중첩된 FE는 자유도에서 제외, 나머지 FE는 (수준수 - 1)만큼 차감
    """
    y = np.asarray(y, dtype=np.float64)
    D = np.asarray(D, dtype=np.float64)
    fe_groups = [np.asarray(g) for g in fe_groups]
    if drop_singleton and len(fe_groups) > 1:
        keep = drop_singletons(fe_groups, len(y))
        if not keep.all():
            y, D = y[keep], D[keep]
            fe_groups = [_codes(g[keep]) for g in fe_groups]
            cluster = _codes(cluster[keep]) if cluster is not None else None
            cluster2 = _codes(cluster2[keep]) if cluster2 is not None else None

    n = len(y)
    # 수렴 판정이 변수 스케일에 좌우되지 않도록 표준화 후 demean, 이후 원단위 복원
    sy = float(y.std()) or 1.0
    sx = float(D.std()) or 1.0
    mat = np.empty((n, 2), dtype=np.float64)
    mat[:, 0] = y / sy
    mat[:, 1] = D / sx
    mat, iters = _demean(mat, fe_groups)
    mat[:, 0] *= sy
    mat[:, 1] *= sx
    yd, xd = mat[:, 0], mat[:, 1]
    xx = float(xd @ xd)
    if xx <= 0:
        raise ValueError("처치 변동이 완전히 흡수됨 (X'X = 0)")
    beta = float(xd @ yd) / xx
    e = yd - beta * xd
    xe = xd * e

    # 자유도: 회귀변수 1 + (cluster에 중첩되지 않은 FE의 수준수 - 1)
    K = 1
    if cluster is not None:
        for g in fe_groups:
            if not _nested_in(g, cluster):
                K += int(g.max()) + 1 - 1

    def crv1(cl):
        G = int(cl.max()) + 1
        adj = (G / (G - 1)) * ((n - 1) / (n - K))
        return adj * _meat(xe, cl) / xx ** 2

    if cluster is None:
        sigma2 = float(e @ e) / (n - K)
        V = sigma2 / xx
    elif cluster2 is None:
        V = crv1(cluster)
    else:                                    # Cameron-Gelbach-Miller 2-way
        V = crv1(cluster) + crv1(cluster2) - crv1(_codes(cluster, cluster2))
    se = float(np.sqrt(max(V, 0)))
    t = beta / se if se > 0 else np.nan
    from scipy import stats
    G = int(cluster.max()) + 1 if cluster is not None else n
    p = float(2 * stats.t.sf(abs(t), df=max(G - 1, 1)))
    return dict(name=name, beta=beta, se=se, t=t, p=p, n=n,
                xx=xx, iters=iters, resid_sd=float(np.sqrt(xx / n)))


def absorb_share(D, fe_groups):
    """FE가 처치 변동을 얼마나 흡수하는지 (1 - 잔여분산/원분산)"""
    v0 = float(np.var(D))
    mat = np.empty((len(D), 1))
    mat[:, 0] = D
    mat, _ = _demean(mat, fe_groups)
    v1 = float(np.var(mat[:, 0]))
    return 1 - v1 / v0, float(np.sqrt(v1))
