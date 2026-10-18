package com.rssreader.app.ui

import android.widget.Toast
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Download
import androidx.compose.material.icons.filled.Home
import androidx.compose.material.icons.filled.RssFeed
import androidx.compose.material3.Icon
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavHostController
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.rssreader.app.vm.AppViewModel

@Composable
fun App(vm: AppViewModel = viewModel()) {
    val nav = rememberNavController()
    val backStackEntry by nav.currentBackStackEntryAsState()
    val route = backStackEntry?.destination?.route
    val topLevel = route == "home" || route == "feeds" || route == "downloads"

    val context = LocalContext.current
    LaunchedEffect(vm.message) {
        vm.message?.let {
            Toast.makeText(context, it, Toast.LENGTH_SHORT).show()
            vm.message = null
        }
    }

    Scaffold(
        bottomBar = {
            if (topLevel) {
                Column {
                    MiniPlayer()
                    NavigationBar {
                        NavigationBarItem(
                            selected = route == "home",
                            onClick = {
                                nav.navigateTop("home")
                            },
                            icon = { Icon(Icons.Filled.Home, null) },
                            label = { Text("Статьи") },
                        )
                        NavigationBarItem(
                            selected = route == "feeds",
                            onClick = { nav.navigateTop("feeds") },
                            icon = { Icon(Icons.Filled.RssFeed, null) },
                            label = { Text("Ленты") },
                        )
                        NavigationBarItem(
                            selected = route == "downloads",
                            onClick = { nav.navigateTop("downloads") },
                            icon = { Icon(Icons.Filled.Download, null) },
                            label = { Text("Загрузки") },
                        )
                    }
                }
            }
        },
    ) { padding ->
        NavHost(
            navController = nav,
            startDestination = "home",
            modifier = Modifier.padding(padding),
        ) {
            composable("home") { ArticlesScreen(vm, nav, null) }
            composable("feeds") { FeedsScreen(vm, nav) }
            composable("downloads") { DownloadsScreen(vm, nav) }
            composable("feed/{id}") { entry ->
                ArticlesScreen(vm, nav, entry.arguments?.getString("id")?.toLongOrNull())
            }
            composable("article/{id}") { entry ->
                ArticleScreen(vm, nav, entry.arguments?.getString("id")?.toLongOrNull() ?: -1L)
            }
            composable("video/{id}") { entry ->
                VideoScreen(vm, nav, entry.arguments?.getString("id")?.toLongOrNull() ?: -1L)
            }
        }
    }
}

private fun NavHostController.navigateTop(route: String) {
    navigate(route) {
        popUpTo("home") { saveState = true }
        launchSingleTop = true
        restoreState = true
    }
}
